from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.enums_finance import EntryKind
from backend.models_finance import Account, Entry, FilterGroup
from backend.schemas_finance import (
    FilterGroupCreate,
    FilterGroupRead,
    FilterGroupRule,
    FilterGroupUpdate,
    FilterRuleCondition,
    FilterRuleGroup,
)
from backend.services.access_scope import account_owner_filter, load_filter_group_for_principal
from backend.services.crud_policy import PolicyViolation
from backend.services.filter_group_rules import (
    FilterEntryContext,
    evaluate_filter_group_rule,
    summarize_filter_group_rule,
)
from backend.services.tags import normalize_tag_color

DEFAULT_FILTER_GROUP_COLORS = {
    "day_to_day": "#0f766e",
    "one_time": "#b45309",
    "fixed": "#1d4ed8",
    "transfers": "#6d28d9",
    "untagged": "#6b7280",
}


@dataclass(frozen=True, slots=True)
class FilterGroupDefinition:
    id: str
    key: str
    name: str
    description: str | None
    color: str | None
    is_default: bool
    position: int
    rule: FilterGroupRule
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class _DefaultFilterGroupSpec:
    key: str
    name: str
    description: str
    color: str
    position: int
    rule: FilterGroupRule


def _condition(
    *,
    field: str,
    operator: str,
    value: str | bool | list[str],
) -> FilterRuleCondition:
    return FilterRuleCondition(field=field, operator=operator, value=value)


def _group(operator: str, *children) -> FilterRuleGroup:
    return FilterRuleGroup(operator=operator, children=list(children))


DEFAULT_FILTER_GROUP_SPECS: tuple[_DefaultFilterGroupSpec, ...] = (
    _DefaultFilterGroupSpec(
        key="day_to_day",
        name="day-to-day",
        description=(
            "Routine living costs such as grocery, dining out, coffee or snacks, "
            "transportation, personal care, pharmacy, alcohol or bars, fitness, "
            "entertainment, subscriptions, home, and pets."
        ),
        color=DEFAULT_FILTER_GROUP_COLORS["day_to_day"],
        position=0,
        rule=FilterGroupRule(
            include=_group(
                "AND",
                _condition(field="entry_kind", operator="is", value="EXPENSE"),
                _condition(
                    field="tags",
                    operator="has_any",
                    value=[
                        "grocery",
                        "dining_out",
                        "coffee_snacks",
                        "transportation",
                        "personal_care",
                        "pharmacy",
                        "alcohol_bars",
                        "fitness",
                        "entertainment",
                        "subscriptions",
                        "home",
                        "pets",
                        "health_medical",
                    ],
                ),
            ),
            exclude=_group(
                "OR",
                _condition(field="tags", operator="has_any", value=["one_time"]),
                _condition(field="is_internal_transfer", operator="is", value=True),
            ),
        ),
    ),
    _DefaultFilterGroupSpec(
        key="one_time",
        name="one-time",
        description=(
            "Irregular or exceptional purchases, primarily identified with the "
            "one_time tag."
        ),
        color=DEFAULT_FILTER_GROUP_COLORS["one_time"],
        position=1,
        rule=FilterGroupRule(
            include=_group(
                "AND",
                _condition(field="entry_kind", operator="is", value="EXPENSE"),
                _condition(field="tags", operator="has_any", value=["one_time"]),
            ),
            exclude=_group(
                "AND",
                _condition(field="is_internal_transfer", operator="is", value=True),
            ),
        ),
    ),
    _DefaultFilterGroupSpec(
        key="fixed",
        name="fixed",
        description=(
            "Predictable recurring obligations such as housing, utilities, "
            "internet or mobile, insurance, interest expense, taxes, and debt payments."
        ),
        color=DEFAULT_FILTER_GROUP_COLORS["fixed"],
        position=2,
        rule=FilterGroupRule(
            include=_group(
                "AND",
                _condition(field="entry_kind", operator="is", value="EXPENSE"),
                _condition(
                    field="tags",
                    operator="has_any",
                    value=[
                        "housing",
                        "utilities",
                        "internet_mobile",
                        "insurance",
                        "interest_expense",
                        "taxes",
                        "debt_payment",
                    ],
                ),
            ),
            exclude=_group(
                "AND",
                _condition(field="is_internal_transfer", operator="is", value=True),
            ),
        ),
    ),
    _DefaultFilterGroupSpec(
        key="transfers",
        name="transfers",
        description=(
            "External transfer-like activity such as e-transfer and cash withdrawal, "
            "kept separate from ordinary spending."
        ),
        color=DEFAULT_FILTER_GROUP_COLORS["transfers"],
        position=3,
        rule=FilterGroupRule(
            include=_group(
                "OR",
                _condition(field="entry_kind", operator="is", value="TRANSFER"),
                _condition(
                    field="tags",
                    operator="has_any",
                    value=["e_transfer", "cash_withdrawal", "savings_investments"],
                ),
            ),
            exclude=_group(
                "AND",
                _condition(field="is_internal_transfer", operator="is", value=True),
            ),
        ),
    ),
    _DefaultFilterGroupSpec(
        key="untagged",
        name="untagged",
        description=(
            "Expense entries that do not match the default day-to-day, one-time, fixed, "
            "or transfer definitions and need review."
        ),
        color=DEFAULT_FILTER_GROUP_COLORS["untagged"],
        position=4,
        rule=FilterGroupRule(
            include=_group(
                "AND",
                _condition(field="entry_kind", operator="is", value="EXPENSE"),
                _condition(
                    field="tags",
                    operator="has_none",
                    value=[
                        "grocery",
                        "dining_out",
                        "coffee_snacks",
                        "transportation",
                        "personal_care",
                        "pharmacy",
                        "alcohol_bars",
                        "fitness",
                        "entertainment",
                        "subscriptions",
                        "home",
                        "pets",
                        "health_medical",
                        "one_time",
                        "housing",
                        "utilities",
                        "internet_mobile",
                        "insurance",
                        "interest_expense",
                        "taxes",
                        "debt_payment",
                        "e_transfer",
                        "cash_withdrawal",
                        "savings_investments",
                    ],
                ),
            ),
            exclude=_group(
                "AND",
                _condition(field="is_internal_transfer", operator="is", value=True),
            ),
        ),
    ),
)


def normalize_filter_group_name(name: str) -> str:
    normalized = " ".join(name.split()).strip()
    if not normalized:
        raise PolicyViolation.bad_request("Filter group name cannot be empty")
    return normalized


def list_filter_group_definitions(
    db: Session,
    *,
    principal: RequestPrincipal,
) -> list[FilterGroupDefinition]:
    ensure_default_filter_groups(db, principal=principal)
    rows = list(
        db.scalars(
            select(FilterGroup)
            .where(FilterGroup.owner_user_id == principal.user_id)
            .order_by(FilterGroup.position.asc(), FilterGroup.created_at.asc())
        )
    )
    return [_build_definition(row) for row in rows]


def list_filter_group_reads(
    db: Session,
    *,
    principal: RequestPrincipal,
) -> list[FilterGroupRead]:
    return [build_filter_group_read(definition) for definition in list_filter_group_definitions(db, principal=principal)]


def get_filter_group_definition(
    db: Session,
    *,
    filter_group_id: str,
    principal: RequestPrincipal,
) -> FilterGroupDefinition:
    row = load_filter_group_for_principal(
        db,
        filter_group_id=filter_group_id,
        principal=principal,
    )
    return _build_definition(row)


def create_filter_group(
    db: Session,
    *,
    payload: FilterGroupCreate,
    principal: RequestPrincipal,
) -> FilterGroupDefinition:
    ensure_default_filter_groups(db, principal=principal)
    normalized_name = normalize_filter_group_name(payload.name)
    _assert_unique_name(db, principal=principal, name=normalized_name)

    next_position = int(
        db.scalar(
            select(func.coalesce(func.max(FilterGroup.position), -1)).where(
                FilterGroup.owner_user_id == principal.user_id
            )
        )
        or -1
    ) + 1

    row = FilterGroup(
        owner_user_id=principal.user_id,
        key=f"custom_{uuid4().hex[:12]}",
        name=normalized_name,
        description=_normalize_optional_text(payload.description),
        color=normalize_tag_color(payload.color),
        is_default=False,
        position=next_position,
        definition_json=payload.rule.model_dump(mode="json"),
    )
    db.add(row)
    db.flush()
    return _build_definition(row)


def update_filter_group(
    db: Session,
    *,
    filter_group_id: str,
    payload: FilterGroupUpdate,
    principal: RequestPrincipal,
) -> FilterGroupDefinition:
    row = load_filter_group_for_principal(
        db,
        filter_group_id=filter_group_id,
        principal=principal,
    )

    if "name" in payload.model_fields_set:
        normalized_name = normalize_filter_group_name(payload.name or "")
        if row.is_default and normalized_name != row.name:
            raise PolicyViolation.conflict("Default filter group names cannot be renamed")
        _assert_unique_name(db, principal=principal, name=normalized_name, current_id=row.id)
        row.name = normalized_name

    if "description" in payload.model_fields_set:
        row.description = _normalize_optional_text(payload.description)
    if "color" in payload.model_fields_set:
        row.color = normalize_tag_color(payload.color)
    if "rule" in payload.model_fields_set and payload.rule is not None:
        row.definition_json = payload.rule.model_dump(mode="json")

    db.add(row)
    db.flush()
    return _build_definition(row)


def delete_filter_group(
    db: Session,
    *,
    filter_group_id: str,
    principal: RequestPrincipal,
) -> None:
    row = load_filter_group_for_principal(
        db,
        filter_group_id=filter_group_id,
        principal=principal,
    )
    if row.is_default:
        raise PolicyViolation.conflict("Default filter groups cannot be deleted")
    db.delete(row)
    db.flush()


def ensure_default_filter_groups(
    db: Session,
    *,
    principal: RequestPrincipal,
) -> None:
    existing_by_key = {
        row.key: row
        for row in db.scalars(
            select(FilterGroup).where(FilterGroup.owner_user_id == principal.user_id)
        )
    }
    missing_rows = []
    for spec in DEFAULT_FILTER_GROUP_SPECS:
        if spec.key in existing_by_key:
            continue
        missing_rows.append(
            FilterGroup(
                owner_user_id=principal.user_id,
                key=spec.key,
                name=spec.name,
                description=spec.description,
                color=spec.color,
                is_default=True,
                position=spec.position,
                definition_json=spec.rule.model_dump(mode="json"),
            )
        )
    if not missing_rows:
        return
    db.add_all(missing_rows)
    db.flush()


def build_filter_group_read(definition: FilterGroupDefinition) -> FilterGroupRead:
    return FilterGroupRead(
        id=definition.id,
        key=definition.key,
        name=definition.name,
        description=definition.description,
        color=definition.color,
        is_default=definition.is_default,
        position=definition.position,
        rule=definition.rule,
        rule_summary=summarize_filter_group_rule(definition.rule),
        created_at=definition.created_at,
        updated_at=definition.updated_at,
    )


def build_filter_group_read_from_row(row: FilterGroup) -> FilterGroupRead:
    return build_filter_group_read(_build_definition(row))


def list_account_entity_ids_for_principal(
    db: Session,
    *,
    principal: RequestPrincipal,
) -> set[str]:
    return {
        entity_id
        for entity_id in db.scalars(
            select(Account.id).where(account_owner_filter(principal))
        ).all()
        if entity_id
    }


def entry_matches_filter_group(
    entry: Entry,
    *,
    filter_group: FilterGroupDefinition,
    account_entity_ids: set[str],
) -> bool:
    context = FilterEntryContext(
        kind=EntryKind(entry.kind),
        tag_names=frozenset(tag.name.strip().lower() for tag in entry.tags if tag.name),
        is_internal_transfer=(
            entry.from_entity_id is not None
            and entry.to_entity_id is not None
            and entry.from_entity_id in account_entity_ids
            and entry.to_entity_id in account_entity_ids
        ),
    )
    return evaluate_filter_group_rule(filter_group.rule, context)


def _assert_unique_name(
    db: Session,
    *,
    principal: RequestPrincipal,
    name: str,
    current_id: str | None = None,
) -> None:
    existing = db.scalar(
        select(FilterGroup).where(
            FilterGroup.owner_user_id == principal.user_id,
            func.lower(FilterGroup.name) == name.lower(),
        )
    )
    if existing is None or existing.id == current_id:
        return
    raise PolicyViolation.conflict("Filter group name already exists")


def _build_definition(row: FilterGroup) -> FilterGroupDefinition:
    return FilterGroupDefinition(
        id=row.id,
        key=row.key,
        name=row.name,
        description=row.description,
        color=row.color,
        is_default=row.is_default,
        position=row.position,
        rule=FilterGroupRule.model_validate(row.definition_json),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None
