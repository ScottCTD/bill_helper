from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from backend.auth import RequestPrincipal
from backend.enums_finance import EntryKind
from backend.enums_finance import GroupMemberRole
from backend.models_finance import Entity, Entry, EntryGroup, EntryGroupMember, Tag
from backend.services.access_scope import (
    ensure_principal_can_assign_user,
    load_account_for_principal,
    load_entry_for_principal,
    load_group_for_principal,
    load_user_for_principal,
)
from backend.services.crud_policy import PolicyViolation, map_value_error
from backend.services.entities import ensure_entity_by_name, normalize_entity_name
from backend.services.groups import entry_group_options, group_tree_options, set_entry_direct_group
from backend.services.tags import generate_random_tag_color
from backend.services.users import ensure_user_by_name, normalize_user_name


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def validate_reference_present(self) -> EntityRef:
        if self.entity_id is None and self.name is None:
            raise ValueError("entity ref requires entity_id or name")
        return self


class EntityRefPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str | None = None
    name: str | None = None


class UserRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = None
    name: str | None = None

    @model_validator(mode="after")
    def validate_reference_present(self) -> UserRef:
        if self.user_id is None and self.name is None:
            raise ValueError("user ref requires user_id or name")
        return self


class UserRefPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str | None = None
    name: str | None = None


class EntryCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str | None = None
    kind: EntryKind
    occurred_at: date
    name: str
    amount_minor: int
    currency_code: str
    from_ref: EntityRef | None = None
    to_ref: EntityRef | None = None
    owner_ref: UserRef | None = None
    markdown_body: str | None = None
    tags: list[str] = Field(default_factory=list)
    direct_group_id: str | None = None
    direct_group_member_role: GroupMemberRole | None = None

    @model_validator(mode="after")
    def validate_direct_group_membership(self) -> EntryCreateCommand:
        if self.direct_group_id is None and self.direct_group_member_role is not None:
            raise ValueError("direct_group_member_role requires direct_group_id.")
        return self


class EntryUpdateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str | None = None
    kind: EntryKind | None = None
    occurred_at: date | None = None
    name: str | None = None
    amount_minor: int | None = None
    currency_code: str | None = None
    from_ref: EntityRefPatch | None = None
    to_ref: EntityRefPatch | None = None
    owner_ref: UserRefPatch | None = None
    markdown_body: str | None = None
    tags: list[str] | None = None
    direct_group_id: str | None = None
    direct_group_member_role: GroupMemberRole | None = None


def signed_amount_minor(kind: EntryKind, amount_minor: int) -> int:
    if kind == EntryKind.INCOME:
        return amount_minor
    return -amount_minor


def normalize_tag_name(name: str) -> str:
    return name.strip().lower()


def normalize_required_tag_name(name: str) -> str:
    normalized = normalize_tag_name(name)
    if not normalized:
        raise ValueError("Tag name cannot be empty")
    return normalized


def ensure_tags(db: Session, tag_names: list[str]) -> list[Tag]:
    normalized_names = sorted({normalize_required_tag_name(name) for name in tag_names})
    if not normalized_names:
        return []

    existing_tags = list(db.scalars(select(Tag).where(Tag.name.in_(normalized_names))))
    existing_by_name = {tag.name: tag for tag in existing_tags}

    tags: list[Tag] = []
    for name in normalized_names:
        tag = existing_by_name.get(name)
        if tag is None:
            tag = Tag(name=name, color=generate_random_tag_color())
            db.add(tag)
            db.flush()
        tags.append(tag)

    return tags


def set_entry_tags(db: Session, entry: Entry, tag_names: list[str]) -> None:
    entry.tags = ensure_tags(db, tag_names)


def soft_delete_entry(db: Session, entry: Entry) -> None:
    entry.is_deleted = True
    entry.deleted_at = utc_now()
    db.execute(
        delete(EntryGroupMember).where(EntryGroupMember.entry_id == entry.id)
    )
    db.flush()


def _normalize_optional_entity_name(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = normalize_entity_name(name)
    return normalized or None


def _normalize_optional_user_name(name: str | None) -> str | None:
    if name is None:
        return None
    normalized = normalize_user_name(name)
    return normalized or None


def _resolve_entity_ref(
    db: Session,
    *,
    ref: EntityRef | EntityRefPatch | None,
    field_name: str,
) -> tuple[str | None, str | None]:
    if ref is None:
        return None, None

    normalized_name = _normalize_optional_entity_name(ref.name)

    if ref.entity_id:
        entity = db.get(Entity, ref.entity_id)
        if entity is None:
            raise PolicyViolation.not_found(f"{field_name} entity not found")
        if normalized_name is not None and entity.name.lower() != normalized_name.lower():
            raise PolicyViolation.bad_request(f"{field_name} entity id and name do not match")
        return entity.id, entity.name

    if normalized_name is not None:
        entity = ensure_entity_by_name(db, normalized_name)
        return entity.id, entity.name

    return None, None


def _resolve_user_ref(
    db: Session,
    *,
    ref: UserRef | UserRefPatch | None,
    field_name: str,
    principal: RequestPrincipal,
) -> tuple[str | None, str | None]:
    if ref is None:
        return None, None

    normalized_name = _normalize_optional_user_name(ref.name)

    if ref.user_id:
        user = load_user_for_principal(db, user_id=ref.user_id, principal=principal)
        if normalized_name is not None and user.name.lower() != normalized_name.lower():
            raise PolicyViolation.bad_request(f"{field_name} user id and name do not match")
        return user.id, user.name

    if normalized_name is not None:
        user = ensure_user_by_name(db, normalized_name)
        ensure_principal_can_assign_user(principal, user_id=user.id)
        return user.id, user.name

    return None, None


def _load_target_group(
    db: Session,
    *,
    group_id: str | None,
    principal: RequestPrincipal,
) -> EntryGroup | None:
    if group_id is None:
        return None
    return load_group_for_principal(
        db,
        group_id=group_id,
        principal=principal,
        stmt=select(EntryGroup).options(*group_tree_options()),
    )


def _load_entry_for_mutation(
    db: Session,
    *,
    entry_id: str,
    principal: RequestPrincipal,
) -> Entry:
    return load_entry_for_principal(
        db,
        entry_id=entry_id,
        principal=principal,
        stmt=select(Entry).options(selectinload(Entry.tags), *entry_group_options()),
    )


def create_entry_from_command(
    db: Session,
    *,
    command: EntryCreateCommand,
    principal: RequestPrincipal,
) -> Entry:
    target_group = _load_target_group(db, group_id=command.direct_group_id, principal=principal)
    if command.account_id is not None:
        load_account_for_principal(db, account_id=command.account_id, principal=principal)

    from_entity_id, from_entity_name = _resolve_entity_ref(
        db,
        ref=command.from_ref,
        field_name="from",
    )
    to_entity_id, to_entity_name = _resolve_entity_ref(
        db,
        ref=command.to_ref,
        field_name="to",
    )

    if command.owner_ref is None:
        owner_user_id = principal.user_id
        owner_name = principal.user_name
    else:
        owner_user_id, owner_name = _resolve_user_ref(
            db,
            ref=command.owner_ref,
            field_name="owner",
            principal=principal,
        )

    entry = Entry(
        account_id=command.account_id,
        kind=command.kind,
        occurred_at=command.occurred_at,
        name=command.name,
        amount_minor=command.amount_minor,
        currency_code=command.currency_code.upper(),
        from_entity_id=from_entity_id,
        to_entity_id=to_entity_id,
        owner_user_id=owner_user_id,
        from_entity=from_entity_name,
        to_entity=to_entity_name,
        owner=owner_name,
        markdown_body=command.markdown_body,
    )
    db.add(entry)
    db.flush()
    set_entry_tags(db, entry, command.tags)
    try:
        set_entry_direct_group(
            db,
            entry=entry,
            group=target_group,
            member_role=command.direct_group_member_role,
        )
    except ValueError as exc:
        raise map_value_error(exc) from exc

    db.flush()
    return entry


def update_entry_from_command(
    db: Session,
    *,
    entry_id: str,
    command: EntryUpdateCommand,
    principal: RequestPrincipal,
) -> Entry:
    entry = _load_entry_for_mutation(db, entry_id=entry_id, principal=principal)
    update_data = command.model_dump(
        exclude_unset=True,
        exclude={"from_ref", "to_ref", "owner_ref"},
    )

    tags = update_data.pop("tags", None)
    group_value = update_data.pop("direct_group_id", Ellipsis)
    role_value = update_data.pop("direct_group_member_role", Ellipsis)

    if "account_id" in update_data and update_data["account_id"] is not None:
        load_account_for_principal(db, account_id=update_data["account_id"], principal=principal)

    if "currency_code" in update_data and update_data["currency_code"] is not None:
        update_data["currency_code"] = update_data["currency_code"].upper()

    if "from_ref" in command.model_fields_set:
        resolved_id, resolved_name = _resolve_entity_ref(
            db,
            ref=command.from_ref,
            field_name="from",
        )
        update_data["from_entity_id"] = resolved_id
        update_data["from_entity"] = resolved_name

    if "to_ref" in command.model_fields_set:
        resolved_id, resolved_name = _resolve_entity_ref(
            db,
            ref=command.to_ref,
            field_name="to",
        )
        update_data["to_entity_id"] = resolved_id
        update_data["to_entity"] = resolved_name

    if "owner_ref" in command.model_fields_set:
        resolved_id, resolved_name = _resolve_user_ref(
            db,
            ref=command.owner_ref,
            field_name="owner",
            principal=principal,
        )
        update_data["owner_user_id"] = resolved_id
        update_data["owner"] = resolved_name

    for field, value in update_data.items():
        setattr(entry, field, value)

    if tags is not None:
        set_entry_tags(db, entry, tags)

    group_update_requested = group_value is not Ellipsis or role_value is not Ellipsis
    if group_update_requested:
        existing_membership = entry.group_membership
        target_group_id = (
            existing_membership.group_id if group_value is Ellipsis and existing_membership is not None else None
        ) if group_value is Ellipsis else group_value
        target_role = (
            existing_membership.member_role if role_value is Ellipsis and existing_membership is not None else None
        ) if role_value is Ellipsis else role_value
        if target_group_id is None:
            target_role = None

        target_group = _load_target_group(db, group_id=target_group_id, principal=principal)

        try:
            set_entry_direct_group(
                db,
                entry=entry,
                group=target_group,
                member_role=target_role,
            )
        except ValueError as exc:
            raise map_value_error(exc) from exc

    db.add(entry)
    db.flush()
    return entry
