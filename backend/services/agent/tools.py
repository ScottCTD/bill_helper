from __future__ import annotations

from dataclasses import dataclass
from datetime import date as DateValue
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from backend.enums import AgentChangeStatus, AgentChangeType
from backend.models import Account, AgentChangeItem, AgentRun, Entity, Entry, Tag
from backend.services.entries import normalize_tag_name
from backend.services.entities import find_entity_by_name, normalize_entity_category, normalize_entity_name
from backend.services.finance import aggregate_monthly_totals, aggregate_top_tags, month_window
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.taxonomy import get_single_term_name_map


@dataclass(slots=True)
class ToolExecutionResult:
    output_text: str
    output_json: dict[str, Any]
    status: str


@dataclass(slots=True)
class ToolContext:
    db: Session
    run_id: str


@dataclass(slots=True)
class AgentToolDefinition:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], ToolExecutionResult]

    @property
    def openai_tool_schema(self) -> dict[str, Any]:
        schema = self.args_model.model_json_schema()
        schema.pop("$defs", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }


class EmptyArgs(BaseModel):
    pass


def _normalize_loose_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _normalize_required_text(value: str) -> str:
    normalized = _normalize_loose_text(value)
    if normalized is None:
        raise ValueError("value cannot be empty")
    return normalized


def _normalize_optional_category(value: str | None) -> str | None:
    return normalize_entity_category(value)


class ListEntriesArgs(BaseModel):
    date: DateValue | None = None
    start_date: DateValue | None = None
    end_date: DateValue | None = None
    name: str | None = None
    from_entity: str | None = None
    to_entity: str | None = None
    tags: list[str] = Field(default_factory=list)
    kind: str | None = Field(default=None, pattern="^(EXPENSE|INCOME)$")
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("name", "from_entity", "to_entity")
    @classmethod
    def normalize_query_text(cls, value: str | None) -> str | None:
        return _normalize_loose_text(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})

    @model_validator(mode="after")
    def validate_date_window(self) -> ListEntriesArgs:
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date cannot be greater than end_date")
        return self


class ListTagsArgs(BaseModel):
    name: str | None = None
    category: str | None = None
    limit: int = Field(default=200, ge=1, le=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        normalized = _normalize_loose_text(value)
        return normalize_tag_name(normalized) if normalized is not None else None

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return _normalize_optional_category(value)


class ListEntitiesArgs(BaseModel):
    name: str | None = None
    category: str | None = None
    limit: int = Field(default=200, ge=1, le=500)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        normalized = _normalize_loose_text(value)
        return normalize_entity_name(normalized) if normalized is not None else None

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return _normalize_optional_category(value)


class ProposeCreateTagArgs(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = _normalize_optional_category(value)
        if normalized is None:
            raise ValueError("category cannot be empty")
        return normalized


class TagPatchArgs(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return _normalize_optional_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> TagPatchArgs:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class ProposeUpdateTagArgs(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    patch: TagPatchArgs

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class ProposeDeleteTagArgs(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class ProposeCreateEntityArgs(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = _normalize_optional_category(value)
        if normalized is None:
            raise ValueError("category cannot be empty")
        return normalized


class EntityPatchArgs(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return _normalize_optional_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> EntityPatchArgs:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class ProposeUpdateEntityArgs(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    patch: EntityPatchArgs

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class ProposeDeleteEntityArgs(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class ProposeCreateEntryArgs(BaseModel):
    kind: str = Field(pattern="^(EXPENSE|INCOME)$")
    date: DateValue
    name: str = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    from_entity: str = Field(min_length=1, max_length=255)
    to_entity: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(default_factory=list)
    markdown_notes: str | None = None

    @field_validator("name", "from_entity", "to_entity")
    @classmethod
    def normalize_entity_fields(cls, value: str) -> str:
        return _normalize_required_text(value)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})


class EntrySelectorArgs(BaseModel):
    date: DateValue
    amount_minor: int = Field(gt=0)
    from_entity: str = Field(min_length=1, max_length=255)
    to_entity: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("from_entity", "to_entity", "name")
    @classmethod
    def normalize_selector_text(cls, value: str) -> str:
        return _normalize_required_text(value)


class EntryPatchArgs(BaseModel):
    kind: str | None = Field(default=None, pattern="^(EXPENSE|INCOME)$")
    date: DateValue | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount_minor: int | None = Field(default=None, gt=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    from_entity: str | None = Field(default=None, min_length=1, max_length=255)
    to_entity: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[str] | None = None
    markdown_notes: str | None = None

    @field_validator("name", "from_entity", "to_entity")
    @classmethod
    def normalize_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_required_text(value)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> EntryPatchArgs:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class ProposeUpdateEntryArgs(BaseModel):
    selector: EntrySelectorArgs
    patch: EntryPatchArgs


class ProposeDeleteEntryArgs(BaseModel):
    selector: EntrySelectorArgs


def _format_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def _string_match_rank(value: str | None, query: str | None) -> tuple[int, bool]:
    if query is None:
        return 0, True
    value_normalized = (_normalize_loose_text(value) or "").lower()
    query_normalized = query.lower()
    if value_normalized == query_normalized:
        return 0, True
    if query_normalized in value_normalized:
        return 1, True
    return 99, False


def _entry_to_public_record(entry: Entry) -> dict[str, Any]:
    tag_names = sorted(normalize_tag_name(tag.name) for tag in entry.tags)
    return {
        "date": entry.occurred_at.isoformat(),
        "kind": entry.kind.value if hasattr(entry.kind, "value") else str(entry.kind),
        "name": entry.name,
        "amount_minor": entry.amount_minor,
        "currency_code": entry.currency_code,
        "from_entity": entry.from_entity,
        "to_entity": entry.to_entity,
        "tags": tag_names,
    }


def _format_entry_record(record: dict[str, Any]) -> str:
    tags = record.get("tags") or []
    return (
        f"{record.get('date')} {record.get('name')} {record.get('amount_minor')} {record.get('currency_code')} "
        f"from={record.get('from_entity') or '-'} to={record.get('to_entity') or '-'} tags={tags}"
    )


def _error_result(summary: str, *, details: Any | None = None) -> ToolExecutionResult:
    payload: dict[str, Any] = {"status": "ERROR", "summary": summary}
    lines = ["ERROR", f"summary: {summary}"]
    if details is not None:
        payload["details"] = details
        lines.append(f"details: {details}")
    return ToolExecutionResult(
        output_text=_format_lines(lines),
        output_json=payload,
        status="error",
    )


def _proposal_result(summary: str, *, preview: dict[str, Any], item: AgentChangeItem) -> ToolExecutionResult:
    output_json = {
        "status": "OK",
        "summary": summary,
        "item_status": item.status.value,
        "preview": preview,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: {summary}",
                f"status: {item.status.value}",
                f"preview: {preview}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _create_change_item(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    rationale_text: str,
) -> AgentChangeItem:
    item = AgentChangeItem(
        run_id=context.run_id,
        change_type=change_type,
        payload_json=payload,
        rationale_text=rationale_text,
        status=AgentChangeStatus.PENDING_REVIEW,
    )
    context.db.add(item)
    context.db.flush()
    return item


def _find_entries_by_selector(context: ToolContext, selector_args: EntrySelectorArgs) -> list[Entry]:
    return list(
        context.db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                Entry.occurred_at == selector_args.date,
                Entry.amount_minor == selector_args.amount_minor,
                func.lower(func.coalesce(Entry.name, "")) == selector_args.name.lower(),
                func.lower(func.coalesce(Entry.from_entity, "")) == selector_args.from_entity.lower(),
                func.lower(func.coalesce(Entry.to_entity, "")) == selector_args.to_entity.lower(),
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.created_at.asc())
        )
    )


def _entry_selector_to_json(selector_args: EntrySelectorArgs) -> dict[str, Any]:
    return {
        "date": selector_args.date.isoformat(),
        "amount_minor": selector_args.amount_minor,
        "from_entity": selector_args.from_entity,
        "to_entity": selector_args.to_entity,
        "name": selector_args.name,
    }


def _entry_ambiguity_details(entries: list[Entry]) -> dict[str, Any]:
    return {
        "candidate_count": len(entries),
        "candidates": [_entry_to_public_record(entry) for entry in entries],
    }


def _list_entries(context: ToolContext, args: ListEntriesArgs) -> ToolExecutionResult:
    conditions = [Entry.is_deleted.is_(False)]
    if args.date is not None:
        conditions.append(Entry.occurred_at == args.date)
    if args.start_date is not None:
        conditions.append(Entry.occurred_at >= args.start_date)
    if args.end_date is not None:
        conditions.append(Entry.occurred_at <= args.end_date)
    if args.kind is not None:
        conditions.append(Entry.kind == args.kind)

    candidate_rows = list(
        context.db.scalars(
            select(Entry)
            .where(*conditions)
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
            .limit(max(args.limit * 8, 200))
        )
    )

    ranked: list[tuple[tuple[int, int, int, int, int, int], Entry]] = []
    for entry in candidate_rows:
        name_rank, name_ok = _string_match_rank(entry.name, args.name)
        from_rank, from_ok = _string_match_rank(entry.from_entity, args.from_entity)
        to_rank, to_ok = _string_match_rank(entry.to_entity, args.to_entity)
        if not (name_ok and from_ok and to_ok):
            continue

        entry_tags = [normalize_tag_name(tag.name) for tag in entry.tags]
        tag_rank = 0
        tag_match = True
        for requested_tag in args.tags:
            best_rank = 99
            matched = False
            for existing_tag in entry_tags:
                current_rank, current_ok = _string_match_rank(existing_tag, requested_tag)
                if current_ok:
                    matched = True
                    best_rank = min(best_rank, current_rank)
            if not matched:
                tag_match = False
                break
            tag_rank += best_rank
        if not tag_match:
            continue

        ranked.append(
            (
                (
                    name_rank,
                    from_rank,
                    to_rank,
                    tag_rank,
                    -entry.occurred_at.toordinal(),
                    int(-entry.created_at.timestamp()),
                ),
                entry,
            )
        )

    ranked.sort(key=lambda pair: pair[0])
    rows = [entry for _, entry in ranked[: args.limit]]
    records = [_entry_to_public_record(entry) for entry in rows]
    entries_text = "; ".join(_format_entry_record(record) for record in records) if records else "(none)"

    output_json = {
        "status": "OK",
        "summary": f"found {len(records)} entries",
        "entries": records,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(records)} entries",
                f"entries: {entries_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _list_tags(context: ToolContext, args: ListTagsArgs) -> ToolExecutionResult:
    tags = list(context.db.scalars(select(Tag).order_by(Tag.name.asc())))
    category_by_tag_id = get_single_term_name_map(
        context.db,
        taxonomy_key="tag_category",
        subject_type="tag",
        subject_ids=[tag.id for tag in tags],
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for tag in tags:
        category = category_by_tag_id.get(str(tag.id))
        name_rank, name_ok = _string_match_rank(tag.name, args.name)
        category_rank, category_ok = _string_match_rank(category, args.category)
        if not (name_ok and category_ok):
            continue
        record = {"name": tag.name, "category": category}
        ranked.append(((name_rank, category_rank, tag.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    records = [record for _, record in ranked[: args.limit]]
    tags_text = ", ".join(f"{tag['name']} ({tag['category'] or 'uncategorized'})" for tag in records) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"found {len(records)} tags",
        "tags": records,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(records)} tags",
                f"tags: {tags_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _list_entities(context: ToolContext, args: ListEntitiesArgs) -> ToolExecutionResult:
    entities = list(context.db.scalars(select(Entity).order_by(func.lower(Entity.name).asc())))
    category_by_entity_id = get_single_term_name_map(
        context.db,
        taxonomy_key="entity_category",
        subject_type="entity",
        subject_ids=[entity.id for entity in entities],
    )

    ranked: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for entity in entities:
        category = category_by_entity_id.get(entity.id) or entity.category
        name_rank, name_ok = _string_match_rank(entity.name, args.name)
        category_rank, category_ok = _string_match_rank(category, args.category)
        if not (name_ok and category_ok):
            continue
        record = {"name": entity.name, "category": category}
        ranked.append(((name_rank, category_rank, entity.name.lower()), record))

    ranked.sort(key=lambda pair: pair[0])
    records = [record for _, record in ranked[: args.limit]]
    entities_text = "; ".join(
        f"{entity['name']} ({entity['category'] or 'uncategorized'})" for entity in records
    ) if records else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"found {len(records)} entities",
        "entities": records,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: found {len(records)} entities",
                f"entities: {entities_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _get_dashboard_summary(context: ToolContext, _: EmptyArgs) -> ToolExecutionResult:
    month = DateValue.today().strftime("%Y-%m")
    start, end = month_window(month)
    expenses, incomes = aggregate_monthly_totals(context.db, start, end)
    top_tags = aggregate_top_tags(context.db, start, end, limit=5)
    top_tags_text = "; ".join(f"{item.tag}:{item.currency_code}:{item.total_minor}" for item in top_tags) if top_tags else "(none)"
    output_json = {
        "status": "OK",
        "summary": f"dashboard snapshot for {month}",
        "expenses_by_currency": expenses,
        "incomes_by_currency": incomes,
        "top_tags": [
            {"tag": item.tag, "currency_code": item.currency_code, "total_minor": item.total_minor}
            for item in top_tags
        ],
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: dashboard snapshot for {month}",
                f"expenses_by_currency: {expenses}",
                f"incomes_by_currency: {incomes}",
                f"top_tags: {top_tags_text}",
            ]
        ),
        output_json=output_json,
        status="ok",
    )


def _propose_create_tag(context: ToolContext, args: ProposeCreateTagArgs) -> ToolExecutionResult:
    existing = context.db.scalar(select(Tag).where(Tag.name == args.name))
    if existing is not None:
        return _error_result("tag already exists", details={"name": args.name})

    payload = {"name": args.name, "category": args.category}
    item = _create_change_item(
        context,
        change_type=AgentChangeType.CREATE_TAG,
        payload=payload,
        rationale_text="Agent proposed creating a tag.",
    )
    return _proposal_result("proposed tag creation", preview=payload, item=item)


def _propose_update_tag(context: ToolContext, args: ProposeUpdateTagArgs) -> ToolExecutionResult:
    existing = context.db.scalar(select(Tag).where(Tag.name == args.name))
    if existing is None:
        return _error_result("tag not found", details={"name": args.name})

    patch = args.patch.model_dump(exclude_unset=True)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = context.db.scalar(select(Tag).where(Tag.name == target_name))
        if duplicate is not None and duplicate.id != existing.id:
            return _error_result("target tag name already exists", details={"name": target_name})

    category_by_tag_id = get_single_term_name_map(
        context.db,
        taxonomy_key="tag_category",
        subject_type="tag",
        subject_ids=[existing.id],
    )
    payload = {
        "name": args.name,
        "patch": patch,
        "current": {
            "name": existing.name,
            "category": category_by_tag_id.get(str(existing.id)),
        },
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_TAG,
        payload=payload,
        rationale_text="Agent proposed updating a tag.",
    )
    preview = {"name": args.name, "patch": patch}
    return _proposal_result("proposed tag update", preview=preview, item=item)


def _propose_delete_tag(context: ToolContext, args: ProposeDeleteTagArgs) -> ToolExecutionResult:
    existing = context.db.scalar(select(Tag).where(Tag.name == args.name))
    if existing is None:
        return _error_result("tag not found", details={"name": args.name})

    impacted_entries = list(
        context.db.scalars(
            select(Entry)
            .join(Entry.tags)
            .where(Tag.id == existing.id, Entry.is_deleted.is_(False))
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
        )
    )
    impact_records = [_entry_to_public_record(entry) for entry in impacted_entries]

    payload = {
        "name": args.name,
        "impact_preview": {
            "entry_count": len(impact_records),
            "entries": impact_records,
        },
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.DELETE_TAG,
        payload=payload,
        rationale_text="Agent proposed deleting a tag.",
    )
    preview = {"name": args.name, "impacted_entries": len(impact_records)}
    return _proposal_result("proposed tag deletion", preview=preview, item=item)


def _propose_create_entity(context: ToolContext, args: ProposeCreateEntityArgs) -> ToolExecutionResult:
    existing = find_entity_by_name(context.db, args.name)
    if existing is not None:
        return _error_result("entity already exists", details={"name": args.name})

    payload = {"name": args.name, "category": args.category}
    item = _create_change_item(
        context,
        change_type=AgentChangeType.CREATE_ENTITY,
        payload=payload,
        rationale_text="Agent proposed creating an entity.",
    )
    return _proposal_result("proposed entity creation", preview=payload, item=item)


def _propose_update_entity(context: ToolContext, args: ProposeUpdateEntityArgs) -> ToolExecutionResult:
    existing = find_entity_by_name(context.db, args.name)
    if existing is None:
        return _error_result("entity not found", details={"name": args.name})

    patch = args.patch.model_dump(exclude_unset=True)
    target_name = patch.get("name")
    if target_name is not None:
        duplicate = find_entity_by_name(context.db, target_name)
        if duplicate is not None and duplicate.id != existing.id:
            return _error_result("target entity name already exists", details={"name": target_name})

    payload = {
        "name": args.name,
        "patch": patch,
        "current": {
            "name": existing.name,
            "category": existing.category,
        },
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_ENTITY,
        payload=payload,
        rationale_text="Agent proposed updating an entity.",
    )
    preview = {"name": args.name, "patch": patch}
    return _proposal_result("proposed entity update", preview=preview, item=item)


def _propose_delete_entity(context: ToolContext, args: ProposeDeleteEntityArgs) -> ToolExecutionResult:
    existing = find_entity_by_name(context.db, args.name)
    if existing is None:
        return _error_result("entity not found", details={"name": args.name})

    impacted_entries = list(
        context.db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                or_(Entry.from_entity_id == existing.id, Entry.to_entity_id == existing.id),
            )
            .options(selectinload(Entry.tags))
            .order_by(Entry.occurred_at.desc(), Entry.created_at.desc())
        )
    )
    impact_records = [_entry_to_public_record(entry) for entry in impacted_entries]
    impacted_account_count = int(
        context.db.scalar(select(func.count(Account.id)).where(Account.entity_id == existing.id))
        or 0
    )

    payload = {
        "name": args.name,
        "impact_preview": {
            "entry_count": len(impact_records),
            "account_count": impacted_account_count,
            "entries": impact_records,
        },
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.DELETE_ENTITY,
        payload=payload,
        rationale_text="Agent proposed deleting an entity.",
    )
    preview = {
        "name": args.name,
        "impacted_entries": len(impact_records),
        "impacted_accounts": impacted_account_count,
    }
    return _proposal_result("proposed entity deletion", preview=preview, item=item)


def _propose_create_entry(context: ToolContext, args: ProposeCreateEntryArgs) -> ToolExecutionResult:
    settings = resolve_runtime_settings(context.db)
    currency_code = (args.currency_code or settings.default_currency_code).strip().upper()
    payload = {
        "kind": args.kind,
        "date": args.date.isoformat(),
        "name": args.name,
        "amount_minor": args.amount_minor,
        "currency_code": currency_code,
        "from_entity": args.from_entity,
        "to_entity": args.to_entity,
        "tags": args.tags,
        "markdown_notes": args.markdown_notes,
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.CREATE_ENTRY,
        payload=payload,
        rationale_text="Agent proposed creating an entry.",
    )
    preview = {
        "date": payload["date"],
        "kind": payload["kind"],
        "name": payload["name"],
        "amount_minor": payload["amount_minor"],
        "currency_code": payload["currency_code"],
        "from_entity": payload["from_entity"],
        "to_entity": payload["to_entity"],
        "tags": payload["tags"],
    }
    return _proposal_result("proposed entry creation", preview=preview, item=item)


def _propose_update_entry(context: ToolContext, args: ProposeUpdateEntryArgs) -> ToolExecutionResult:
    matches = _find_entries_by_selector(context, args.selector)
    if not matches:
        return _error_result(
            "no entry matched selector",
            details={"selector": _entry_selector_to_json(args.selector)},
        )
    if len(matches) > 1:
        return _error_result(
            "ambiguous selector matched multiple entries; ask the user to clarify",
            details={
                "selector": _entry_selector_to_json(args.selector),
                **_entry_ambiguity_details(matches),
            },
        )

    patch = args.patch.model_dump(exclude_unset=True)
    if "date" in patch and patch["date"] is not None:
        patch["date"] = patch["date"].isoformat()

    payload = {
        "selector": _entry_selector_to_json(args.selector),
        "patch": patch,
        "target": _entry_to_public_record(matches[0]),
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.UPDATE_ENTRY,
        payload=payload,
        rationale_text="Agent proposed updating an entry.",
    )
    preview = {
        "selector": payload["selector"],
        "patch": patch,
    }
    return _proposal_result("proposed entry update", preview=preview, item=item)


def _propose_delete_entry(context: ToolContext, args: ProposeDeleteEntryArgs) -> ToolExecutionResult:
    matches = _find_entries_by_selector(context, args.selector)
    if not matches:
        return _error_result(
            "no entry matched selector",
            details={"selector": _entry_selector_to_json(args.selector)},
        )
    if len(matches) > 1:
        return _error_result(
            "ambiguous selector matched multiple entries; ask the user to clarify",
            details={
                "selector": _entry_selector_to_json(args.selector),
                **_entry_ambiguity_details(matches),
            },
        )

    payload = {
        "selector": _entry_selector_to_json(args.selector),
        "target": _entry_to_public_record(matches[0]),
    }
    item = _create_change_item(
        context,
        change_type=AgentChangeType.DELETE_ENTRY,
        payload=payload,
        rationale_text="Agent proposed deleting an entry.",
    )
    preview = {
        "selector": payload["selector"],
        "target": payload["target"],
    }
    return _proposal_result("proposed entry deletion", preview=preview, item=item)


TOOLS: dict[str, AgentToolDefinition] = {
    "list_entries": AgentToolDefinition(
        name="list_entries",
        description=(
            "List/query entries by date, date range, name, from_entity, to_entity, tags, and kind. "
            "When name/from/to filters are present, exact matches are ranked higher than fuzzy matches. "
            "This tool is read-only and never mutates data."
        ),
        args_model=ListEntriesArgs,
        handler=_list_entries,
    ),
    "list_tags": AgentToolDefinition(
        name="list_tags",
        description=(
            "List/query tags by name and category. Exact matches are ranked higher than fuzzy matches. "
            "This tool is read-only and includes tag categories."
        ),
        args_model=ListTagsArgs,
        handler=_list_tags,
    ),
    "list_entities": AgentToolDefinition(
        name="list_entities",
        description=(
            "List/query entities by name and category. Exact matches are ranked higher than fuzzy matches. "
            "Use category='account' when looking for account entities. This tool is read-only."
        ),
        args_model=ListEntitiesArgs,
        handler=_list_entities,
    ),
    "get_dashboard_summary": AgentToolDefinition(
        name="get_dashboard_summary",
        description=(
            "Get a compact dashboard snapshot for the current month. "
            "Use this for high-level Q&A context. This tool is read-only."
        ),
        args_model=EmptyArgs,
        handler=_get_dashboard_summary,
    ),
    "propose_create_tag": AgentToolDefinition(
        name="propose_create_tag",
        description=(
            "Create a review-gated proposal to add a new tag. "
            "This does not mutate tags immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateTagArgs,
        handler=_propose_create_tag,
    ),
    "propose_update_tag": AgentToolDefinition(
        name="propose_update_tag",
        description=(
            "Create a review-gated proposal to rename a tag and/or update its category. "
            "This does not mutate tags immediately; it creates a pending review item only."
        ),
        args_model=ProposeUpdateTagArgs,
        handler=_propose_update_tag,
    ),
    "propose_delete_tag": AgentToolDefinition(
        name="propose_delete_tag",
        description=(
            "Create a review-gated proposal to delete a tag. "
            "Delete behavior detaches tag references from entries; it does not delete entries."
        ),
        args_model=ProposeDeleteTagArgs,
        handler=_propose_delete_tag,
    ),
    "propose_create_entity": AgentToolDefinition(
        name="propose_create_entity",
        description=(
            "Create a review-gated proposal to add a new entity. "
            "This does not mutate entities immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateEntityArgs,
        handler=_propose_create_entity,
    ),
    "propose_update_entity": AgentToolDefinition(
        name="propose_update_entity",
        description=(
            "Create a review-gated proposal to rename an entity and/or update its category. "
            "This does not mutate entities immediately; it creates a pending review item only."
        ),
        args_model=ProposeUpdateEntityArgs,
        handler=_propose_update_entity,
    ),
    "propose_delete_entity": AgentToolDefinition(
        name="propose_delete_entity",
        description=(
            "Create a review-gated proposal to delete an entity. "
            "Delete behavior detaches nullable references from entries/accounts; it does not delete entries/accounts."
        ),
        args_model=ProposeDeleteEntityArgs,
        handler=_propose_delete_entity,
    ),
    "propose_create_entry": AgentToolDefinition(
        name="propose_create_entry",
        description=(
            "Create a review-gated proposal to add a new entry. "
            "This does not mutate entries immediately; it creates a pending review item only."
        ),
        args_model=ProposeCreateEntryArgs,
        handler=_propose_create_entry,
    ),
    "propose_update_entry": AgentToolDefinition(
        name="propose_update_entry",
        description=(
            "Create a review-gated proposal to update an existing entry selected by date/amount/name/from/to. "
            "If selector matches multiple entries, the tool reports ambiguity so the user can clarify."
        ),
        args_model=ProposeUpdateEntryArgs,
        handler=_propose_update_entry,
    ),
    "propose_delete_entry": AgentToolDefinition(
        name="propose_delete_entry",
        description=(
            "Create a review-gated proposal to delete an existing entry selected by date/amount/name/from/to. "
            "If selector matches multiple entries, the tool reports ambiguity so the user can clarify."
        ),
        args_model=ProposeDeleteEntryArgs,
        handler=_propose_delete_entry,
    ),
}


def build_openai_tool_schemas() -> list[dict[str, Any]]:
    return [tool.openai_tool_schema for tool in TOOLS.values()]


def _pending_review_count_for_other_runs(context: ToolContext) -> int:
    thread_id = context.db.scalar(select(AgentRun.thread_id).where(AgentRun.id == context.run_id))
    if thread_id is None:
        return 0
    return int(
        context.db.scalar(
            select(func.count(AgentChangeItem.id))
            .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
            .where(
                AgentRun.thread_id == thread_id,
                AgentChangeItem.status == AgentChangeStatus.PENDING_REVIEW,
                AgentChangeItem.run_id != context.run_id,
            )
        )
        or 0
    )


def execute_tool(name: str, arguments: dict[str, Any], context: ToolContext) -> ToolExecutionResult:
    definition = TOOLS.get(name)
    if definition is None:
        return _error_result(f"unknown tool '{name}'")

    if name.startswith("propose_"):
        pending_count = _pending_review_count_for_other_runs(context)
        if pending_count > 0:
            return _error_result(
                "proposal tools are blocked until pending review items are reviewed",
                details={
                    "pending_review_count": pending_count,
                    "instruction": (
                        "Ask the user to review pending proposal items (approve/reject), then continue with new proposals."
                    ),
                },
            )

    try:
        parsed = definition.args_model.model_validate(arguments)
    except ValidationError as exc:
        return _error_result("invalid tool arguments", details=exc.errors())

    settings = resolve_runtime_settings(context.db)
    retrying = Retrying(
        stop=stop_after_attempt(settings.agent_retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.agent_retry_initial_wait_seconds,
            max=settings.agent_retry_max_wait_seconds,
            exp_base=settings.agent_retry_backoff_multiplier,
        ),
        retry=retry_if_exception(lambda exc: not isinstance(exc, ValueError)),
        reraise=True,
    )

    try:
        result = None
        for attempt in retrying:
            with attempt:
                result = definition.handler(context, parsed)
        if result is None:  # pragma: no cover - defensive guard
            return _error_result("tool execution failed", details="no result returned")
        return result
    except ValueError as exc:
        return _error_result("tool execution failed", details=str(exc))
    except Exception as exc:  # pragma: no cover - guarded for runtime resilience
        return _error_result("tool execution failed", details=str(exc))
