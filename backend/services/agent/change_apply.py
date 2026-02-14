from __future__ import annotations

from dataclasses import dataclass
from datetime import date as DateValue
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.enums import AgentChangeType, EntryKind
from backend.models import Account, Entity, Entry, Tag
from backend.services.entries import normalize_tag_name, set_entry_tags, soft_delete_entry
from backend.services.entities import (
    find_entity_by_name,
    get_or_create_entity,
    normalize_entity_category,
    normalize_entity_name,
    set_entity_category,
)
from backend.services.groups import assign_initial_group, recompute_entry_groups
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.tags import resolve_tag_color
from backend.services.taxonomy import assign_single_term_by_name
from backend.services.users import ensure_current_user


@dataclass(frozen=True, slots=True)
class AppliedResource:
    resource_type: str
    resource_id: str


ChangeApplyHandler = Callable[[Session, dict[str, Any]], AppliedResource]


TAG_CATEGORY_TAXONOMY_KEY = "tag_category"
TAG_CATEGORY_SUBJECT_TYPE = "tag"
ENTITY_CATEGORY_TAXONOMY_KEY = "entity_category"
ENTITY_CATEGORY_SUBJECT_TYPE = "entity"


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


class CreateTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = normalize_entity_category(value)
        if normalized is None:
            raise ValueError("Tag category cannot be empty")
        return normalized


class UpdateTagPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    category: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return normalize_entity_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateTagPatchPayload:
        if not self.model_fields_set:
            raise ValueError("Tag patch must include at least one field")
        return self


class UpdateTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    patch: UpdateTagPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        return normalized


class DeleteTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("Tag name cannot be empty")
        return normalized


class CreateEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("Entity name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = normalize_entity_category(value)
        if normalized is None:
            raise ValueError("Entity category cannot be empty")
        return normalized


class UpdateEntityPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("Entity name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return normalize_entity_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateEntityPatchPayload:
        if not self.model_fields_set:
            raise ValueError("Entity patch must include at least one field")
        return self


class UpdateEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    patch: UpdateEntityPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("Entity name cannot be empty")
        return normalized


class DeleteEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("Entity name cannot be empty")
        return normalized


class CreateEntryPayload(BaseModel):
    kind: EntryKind
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
    def normalize_required_text(cls, value: str) -> str:
        normalized = _normalize_text(value)
        if normalized is None:
            raise ValueError("Entry text fields cannot be empty")
        return normalized

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


class EntrySelectorPayload(BaseModel):
    date: DateValue
    amount_minor: int = Field(gt=0)
    from_entity: str = Field(min_length=1, max_length=255)
    to_entity: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("from_entity", "to_entity", "name")
    @classmethod
    def normalize_selector_text(cls, value: str) -> str:
        normalized = _normalize_text(value)
        if normalized is None:
            raise ValueError("Entry selector fields cannot be empty")
        return normalized


class UpdateEntryPatchPayload(BaseModel):
    kind: EntryKind | None = None
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
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = _normalize_text(value)
        if normalized is None:
            raise ValueError("Entry patch text fields cannot be empty")
        return normalized

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
    def ensure_any_field_set(self) -> UpdateEntryPatchPayload:
        if not self.model_fields_set:
            raise ValueError("Entry patch must include at least one field")
        return self


class UpdateEntryPayload(BaseModel):
    selector: EntrySelectorPayload
    patch: UpdateEntryPatchPayload


class DeleteEntryPayload(BaseModel):
    selector: EntrySelectorPayload


def _find_entries_by_selector(db: Session, selector_payload: EntrySelectorPayload) -> list[Entry]:
    return list(
        db.scalars(
            select(Entry)
            .where(
                Entry.is_deleted.is_(False),
                Entry.occurred_at == selector_payload.date,
                Entry.amount_minor == selector_payload.amount_minor,
                func.lower(func.coalesce(Entry.name, "")) == selector_payload.name.lower(),
                func.lower(func.coalesce(Entry.from_entity, "")) == selector_payload.from_entity.lower(),
                func.lower(func.coalesce(Entry.to_entity, "")) == selector_payload.to_entity.lower(),
            )
            .order_by(Entry.created_at.asc())
        )
    )


def _entry_public_summary(entry: Entry) -> str:
    return (
        f"{entry.occurred_at.isoformat()} {entry.name} {entry.amount_minor} {entry.currency_code} "
        f"from={entry.from_entity or '-'} to={entry.to_entity or '-'}"
    )


def _find_unique_entry_by_selector(db: Session, selector_payload: EntrySelectorPayload) -> Entry:
    matches = _find_entries_by_selector(db, selector_payload)
    if not matches:
        raise ValueError("Entry selector did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(_entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry selector is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def apply_create_tag(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = CreateTagPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    existing = db.scalar(select(Tag).where(Tag.name == parsed.name))
    if existing is not None:
        return AppliedResource(resource_type="tag", resource_id=str(existing.id))

    tag = Tag(name=parsed.name, color=resolve_tag_color(None))
    db.add(tag)
    db.flush()
    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_CATEGORY_TAXONOMY_KEY,
        subject_type=TAG_CATEGORY_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=parsed.category,
    )
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_update_tag(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = UpdateTagPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    tag = db.scalar(select(Tag).where(Tag.name == parsed.name))
    if tag is None:
        raise ValueError("Tag not found")

    if "name" in parsed.patch.model_fields_set and parsed.patch.name is not None:
        existing = db.scalar(select(Tag).where(Tag.name == parsed.patch.name))
        if existing is not None and existing.id != tag.id:
            raise ValueError("Tag already exists")
        tag.name = parsed.patch.name

    if "category" in parsed.patch.model_fields_set:
        assign_single_term_by_name(
            db,
            taxonomy_key=TAG_CATEGORY_TAXONOMY_KEY,
            subject_type=TAG_CATEGORY_SUBJECT_TYPE,
            subject_id=tag.id,
            term_name=parsed.patch.category,
        )

    db.add(tag)
    db.flush()
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_delete_tag(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = DeleteTagPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    tag = db.scalar(select(Tag).where(Tag.name == parsed.name))
    if tag is None:
        raise ValueError("Tag not found")

    referenced_entry_count = int(
        db.scalar(
            select(func.count(Entry.id))
            .join(Entry.tags)
            .where(Tag.id == tag.id, Entry.is_deleted.is_(False))
        )
        or 0
    )
    if referenced_entry_count > 0:
        noun = "entry" if referenced_entry_count == 1 else "entries"
        raise ValueError(f"Tag cannot be deleted because it is referenced by {referenced_entry_count} {noun}")

    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_CATEGORY_TAXONOMY_KEY,
        subject_type=TAG_CATEGORY_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=None,
    )
    resource_id = str(tag.id)
    db.delete(tag)
    db.flush()
    return AppliedResource(resource_type="tag", resource_id=resource_id)


def apply_create_entity(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = CreateEntityPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    entity = get_or_create_entity(db, parsed.name, category=parsed.category)
    db.flush()
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_update_entity(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = UpdateEntityPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    entity = find_entity_by_name(db, parsed.name)
    if entity is None:
        raise ValueError("Entity not found")

    if "name" in parsed.patch.model_fields_set and parsed.patch.name is not None:
        existing = find_entity_by_name(db, parsed.patch.name)
        if existing is not None and existing.id != entity.id:
            raise ValueError("Entity name already exists")
        entity.name = parsed.patch.name
        db.execute(update(Entry).where(Entry.from_entity_id == entity.id).values(from_entity=parsed.patch.name))
        db.execute(update(Entry).where(Entry.to_entity_id == entity.id).values(to_entity=parsed.patch.name))

    if "category" in parsed.patch.model_fields_set:
        set_entity_category(db, entity, parsed.patch.category)

    db.add(entity)
    db.flush()
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_delete_entity(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = DeleteEntityPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    entity = find_entity_by_name(db, parsed.name)
    if entity is None:
        raise ValueError("Entity not found")

    db.execute(update(Entry).where(Entry.from_entity_id == entity.id).values(from_entity_id=None, from_entity=None))
    db.execute(update(Entry).where(Entry.to_entity_id == entity.id).values(to_entity_id=None, to_entity=None))
    db.execute(update(Account).where(Account.entity_id == entity.id).values(entity_id=None))
    assign_single_term_by_name(
        db,
        taxonomy_key=ENTITY_CATEGORY_TAXONOMY_KEY,
        subject_type=ENTITY_CATEGORY_SUBJECT_TYPE,
        subject_id=entity.id,
        term_name=None,
    )

    resource_id = entity.id
    db.delete(entity)
    db.flush()
    return AppliedResource(resource_type="entity", resource_id=resource_id)


def apply_create_entry(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = CreateEntryPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    settings = resolve_runtime_settings(db)
    currency_code = (parsed.currency_code or settings.default_currency_code).strip().upper()

    from_entity = get_or_create_entity(db, parsed.from_entity)
    to_entity = get_or_create_entity(db, parsed.to_entity)

    owner_user = ensure_current_user(db, settings.current_user_name)

    entry = Entry(
        account_id=None,
        kind=parsed.kind,
        occurred_at=parsed.date,
        name=parsed.name,
        amount_minor=parsed.amount_minor,
        currency_code=currency_code,
        from_entity_id=from_entity.id,
        to_entity_id=to_entity.id,
        owner_user_id=owner_user.id,
        from_entity=from_entity.name,
        to_entity=to_entity.name,
        owner=owner_user.name,
        markdown_body=parsed.markdown_notes,
        group_id="",
    )
    db.add(entry)
    assign_initial_group(db, entry)
    set_entry_tags(db, entry, parsed.tags)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_update_entry(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = UpdateEntryPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    entry = _find_unique_entry_by_selector(db, parsed.selector)

    if "kind" in parsed.patch.model_fields_set and parsed.patch.kind is not None:
        entry.kind = parsed.patch.kind
    if "date" in parsed.patch.model_fields_set and parsed.patch.date is not None:
        entry.occurred_at = parsed.patch.date
    if "name" in parsed.patch.model_fields_set and parsed.patch.name is not None:
        entry.name = parsed.patch.name
    if "amount_minor" in parsed.patch.model_fields_set and parsed.patch.amount_minor is not None:
        entry.amount_minor = parsed.patch.amount_minor
    if "currency_code" in parsed.patch.model_fields_set and parsed.patch.currency_code is not None:
        entry.currency_code = parsed.patch.currency_code

    if "from_entity" in parsed.patch.model_fields_set:
        if parsed.patch.from_entity is None:
            entry.from_entity_id = None
            entry.from_entity = None
        else:
            from_entity = get_or_create_entity(db, parsed.patch.from_entity)
            entry.from_entity_id = from_entity.id
            entry.from_entity = from_entity.name

    if "to_entity" in parsed.patch.model_fields_set:
        if parsed.patch.to_entity is None:
            entry.to_entity_id = None
            entry.to_entity = None
        else:
            to_entity = get_or_create_entity(db, parsed.patch.to_entity)
            entry.to_entity_id = to_entity.id
            entry.to_entity = to_entity.name

    if "markdown_notes" in parsed.patch.model_fields_set:
        entry.markdown_body = parsed.patch.markdown_notes

    if "tags" in parsed.patch.model_fields_set:
        set_entry_tags(db, entry, parsed.patch.tags or [])

    db.add(entry)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_delete_entry(db: Session, payload: dict[str, Any]) -> AppliedResource:
    try:
        parsed = DeleteEntryPayload.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc

    entry = _find_unique_entry_by_selector(db, parsed.selector)
    soft_delete_entry(db, entry)
    recompute_entry_groups(db)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


APPLY_CHANGE_HANDLERS: dict[AgentChangeType, ChangeApplyHandler] = {
    AgentChangeType.CREATE_ENTRY: apply_create_entry,
    AgentChangeType.UPDATE_ENTRY: apply_update_entry,
    AgentChangeType.DELETE_ENTRY: apply_delete_entry,
    AgentChangeType.CREATE_TAG: apply_create_tag,
    AgentChangeType.UPDATE_TAG: apply_update_tag,
    AgentChangeType.DELETE_TAG: apply_delete_tag,
    AgentChangeType.CREATE_ENTITY: apply_create_entity,
    AgentChangeType.UPDATE_ENTITY: apply_update_entity,
    AgentChangeType.DELETE_ENTITY: apply_delete_entity,
}


def apply_change_item_payload(db: Session, *, change_type: AgentChangeType, payload: dict[str, Any]) -> AppliedResource:
    handler = APPLY_CHANGE_HANDLERS.get(change_type)
    if handler is None:  # pragma: no cover - enum guard
        raise ValueError(f"Unsupported change type: {change_type}")
    return handler(db, payload)
