from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeType
from backend.models_finance import Entry, Tag
from backend.services.agent.change_contracts import (
    CreateEntryPayload,
    CreateEntityPayload,
    CreateTagPayload,
    DeleteEntryPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    EntrySelectorPayload,
    UpdateEntryPayload,
    UpdateEntityPayload,
    UpdateTagPayload,
    validate_change_payload,
)
from backend.services.crud_policy import PolicyViolation
from backend.services.entries import set_entry_tags, soft_delete_entry
from backend.services.entities import (
    delete_entity_and_preserve_labels,
    ensure_entity_by_name,
    ensure_entity_is_not_account_backed,
    find_entity_by_name,
    set_entity_category,
)
from backend.services.tags import delete_tag
from backend.services.groups import assign_initial_group, recompute_entry_groups
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.tags import resolve_tag_color
from backend.services.taxonomy_constants import (
    ENTITY_CATEGORY_SUBJECT_TYPE,
    ENTITY_CATEGORY_TAXONOMY_KEY,
    TAG_TYPE_SUBJECT_TYPE,
    TAG_TYPE_TAXONOMY_KEY,
)
from backend.services.taxonomy import assign_single_term_by_name
from backend.services.users import ensure_current_user


@dataclass(frozen=True, slots=True)
class AppliedResource:
    resource_type: str
    resource_id: str


ChangeApplyHandler = Callable[[Session, dict[str, Any]], AppliedResource]


TChangePayload = TypeVar("TChangePayload", bound=BaseModel)


def _parse_payload(
    payload: dict[str, Any],
    *,
    change_type: AgentChangeType,
    model_type: type[TChangePayload],
) -> TChangePayload:
    try:
        parsed = validate_change_payload(change_type, payload)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(parsed, model_type):  # pragma: no cover - enum/model map guard
        raise ValueError(f"Unexpected payload model for change type {change_type.value}")
    return parsed


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
    parsed = _parse_payload(payload, change_type=AgentChangeType.CREATE_TAG, model_type=CreateTagPayload)

    existing = db.scalar(select(Tag).where(Tag.name == parsed.name))
    if existing is not None:
        return AppliedResource(resource_type="tag", resource_id=str(existing.id))

    tag = Tag(name=parsed.name, color=resolve_tag_color(None))
    db.add(tag)
    db.flush()
    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=parsed.type,
    )
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_update_tag(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.UPDATE_TAG, model_type=UpdateTagPayload)

    tag = db.scalar(select(Tag).where(Tag.name == parsed.name))
    if tag is None:
        raise ValueError("Tag not found")

    if "name" in parsed.patch.model_fields_set and parsed.patch.name is not None:
        existing = db.scalar(select(Tag).where(Tag.name == parsed.patch.name))
        if existing is not None and existing.id != tag.id:
            raise ValueError("Tag already exists")
        tag.name = parsed.patch.name

    if "type" in parsed.patch.model_fields_set:
        assign_single_term_by_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
            term_name=parsed.patch.type,
        )

    db.add(tag)
    db.flush()
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_delete_tag(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.DELETE_TAG, model_type=DeleteTagPayload)

    tag = db.scalar(select(Tag).where(Tag.name == parsed.name))
    if tag is None:
        raise ValueError("Tag not found")

    resource_id = str(tag.id)
    delete_tag(db, tag=tag)
    return AppliedResource(resource_type="tag", resource_id=resource_id)


def apply_create_entity(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.CREATE_ENTITY, model_type=CreateEntityPayload)

    entity = ensure_entity_by_name(db, parsed.name, category=parsed.category)
    db.flush()
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_update_entity(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.UPDATE_ENTITY, model_type=UpdateEntityPayload)

    entity = find_entity_by_name(db, parsed.name)
    if entity is None:
        raise ValueError("Entity not found")
    try:
        ensure_entity_is_not_account_backed(entity)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc

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
    parsed = _parse_payload(payload, change_type=AgentChangeType.DELETE_ENTITY, model_type=DeleteEntityPayload)

    entity = find_entity_by_name(db, parsed.name)
    if entity is None:
        raise ValueError("Entity not found")

    resource_id = entity.id
    try:
        delete_entity_and_preserve_labels(db, entity=entity)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=resource_id)


def apply_create_entry(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.CREATE_ENTRY, model_type=CreateEntryPayload)

    settings = resolve_runtime_settings(db)
    currency_code = (parsed.currency_code or settings.default_currency_code).strip().upper()

    from_entity = ensure_entity_by_name(db, parsed.from_entity)
    to_entity = ensure_entity_by_name(db, parsed.to_entity)

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
    parsed = _parse_payload(payload, change_type=AgentChangeType.UPDATE_ENTRY, model_type=UpdateEntryPayload)

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
            from_entity = ensure_entity_by_name(db, parsed.patch.from_entity)
            entry.from_entity_id = from_entity.id
            entry.from_entity = from_entity.name

    if "to_entity" in parsed.patch.model_fields_set:
        if parsed.patch.to_entity is None:
            entry.to_entity_id = None
            entry.to_entity = None
        else:
            to_entity = ensure_entity_by_name(db, parsed.patch.to_entity)
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
    parsed = _parse_payload(payload, change_type=AgentChangeType.DELETE_ENTRY, model_type=DeleteEntryPayload)

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
