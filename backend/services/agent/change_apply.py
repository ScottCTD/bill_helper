from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry, EntryGroup, EntryGroupMember, Tag
from backend.services.agent.change_contracts import (
    CreateGroupMemberPayload,
    CreateGroupPayload,
    CreateEntryPayload,
    CreateEntityPayload,
    CreateTagPayload,
    DeleteGroupMemberPayload,
    DeleteGroupPayload,
    DeleteEntryPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    EntryReferencePayload,
    EntrySelectorPayload,
    GroupReferencePayload,
    UpdateGroupPayload,
    UpdateEntryPayload,
    UpdateEntityPayload,
    UpdateTagPayload,
    validate_change_payload,
)
from backend.services.agent.entry_references import (
    entry_public_summary,
    find_entries_by_id,
    find_entries_by_selector,
)
from backend.services.agent.group_references import group_owner_condition
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
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.groups import (
    add_group_member,
    create_group,
    delete_group,
    group_tree_options,
    load_group_tree,
    remove_group_member,
    rename_group,
)
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


def _find_unique_entry_by_selector(db: Session, selector_payload: EntrySelectorPayload) -> Entry:
    matches = find_entries_by_selector(db, selector_payload)
    if not matches:
        raise ValueError("Entry selector did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry selector is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def _find_unique_entry_by_id(db: Session, entry_id: str) -> Entry:
    matches = find_entries_by_id(db, entry_id)
    if not matches:
        raise ValueError("Entry id did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry.id for entry in matches)
        raise ValueError(f"Entry id is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def _find_change_item_by_id(db: Session, change_item_id: str) -> AgentChangeItem:
    item = db.get(AgentChangeItem, change_item_id)
    if item is None:
        raise ValueError(f"Referenced proposal not found: {change_item_id}")
    return item


def _resolve_applied_group_id(db: Session, reference: GroupReferencePayload) -> str:
    if reference.group_id is not None:
        return reference.group_id

    assert reference.create_group_proposal_id is not None
    item = _find_change_item_by_id(db, reference.create_group_proposal_id)
    if item.change_type != AgentChangeType.CREATE_GROUP:
        raise ValueError("Referenced proposal is not a create_group proposal")
    if item.applied_resource_type != "group" or item.applied_resource_id is None:
        raise ValueError("Referenced group proposal has not been applied yet")
    return item.applied_resource_id


def _resolve_applied_entry_id(db: Session, reference: EntryReferencePayload) -> str:
    if reference.entry_id is not None:
        return reference.entry_id

    assert reference.create_entry_proposal_id is not None
    item = _find_change_item_by_id(db, reference.create_entry_proposal_id)
    if item.change_type != AgentChangeType.CREATE_ENTRY:
        raise ValueError("Referenced proposal is not a create_entry proposal")
    if item.applied_resource_type != "entry" or item.applied_resource_id is None:
        raise ValueError("Referenced entry proposal has not been applied yet")
    return item.applied_resource_id


def _find_scoped_group_by_id(db: Session, *, group_id: str, current_user_id: str) -> EntryGroup:
    group = db.scalar(
        select(EntryGroup)
        .where(
            EntryGroup.id == group_id,
            group_owner_condition(current_user_id),
        )
        .options(*group_tree_options())
    )
    if group is None:
        raise ValueError("Group not found")
    return group


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
    )
    db.add(entry)
    set_entry_tags(db, entry, parsed.tags)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_update_entry(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.UPDATE_ENTRY, model_type=UpdateEntryPayload)

    if parsed.entry_id is not None:
        entry = _find_unique_entry_by_id(db, parsed.entry_id)
    elif parsed.selector is not None:
        entry = _find_unique_entry_by_selector(db, parsed.selector)
    else:  # pragma: no cover - validated by Pydantic
        raise ValueError("Entry reference is required")

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

    if parsed.entry_id is not None:
        entry = _find_unique_entry_by_id(db, parsed.entry_id)
    elif parsed.selector is not None:
        entry = _find_unique_entry_by_selector(db, parsed.selector)
    else:  # pragma: no cover - validated by Pydantic
        raise ValueError("Entry reference is required")
    soft_delete_entry(db, entry)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_create_group(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.CREATE_GROUP, model_type=CreateGroupPayload)

    settings = resolve_runtime_settings(db)
    owner_user = ensure_current_user(db, settings.current_user_name)
    group = create_group(
        db,
        name=parsed.name,
        group_type=parsed.group_type,
        owner_user_id=owner_user.id,
    )
    db.flush()
    return AppliedResource(resource_type="group", resource_id=group.id)


def apply_update_group(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.UPDATE_GROUP, model_type=UpdateGroupPayload)

    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group = _find_scoped_group_by_id(db, group_id=parsed.group_id, current_user_id=current_user.id)
    updated = rename_group(db, group=group, name=parsed.patch.name or group.name)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=updated.id)


def apply_delete_group(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(payload, change_type=AgentChangeType.DELETE_GROUP, model_type=DeleteGroupPayload)

    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group = _find_scoped_group_by_id(db, group_id=parsed.group_id, current_user_id=current_user.id)
    resource_id = group.id
    delete_group(db, group=group)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=resource_id)


def apply_create_group_member(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(
        payload,
        change_type=AgentChangeType.CREATE_GROUP_MEMBER,
        model_type=CreateGroupMemberPayload,
    )

    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group_id = _resolve_applied_group_id(db, parsed.group_ref)
    group = _find_scoped_group_by_id(db, group_id=group_id, current_user_id=current_user.id)

    entry = None
    child_group = None
    if parsed.entry_ref is not None:
        entry_id = _resolve_applied_entry_id(db, parsed.entry_ref)
        entry = _find_unique_entry_by_id(db, entry_id)
    if parsed.child_group_ref is not None:
        child_group_id = _resolve_applied_group_id(db, parsed.child_group_ref)
        child_group = _find_scoped_group_by_id(db, group_id=child_group_id, current_user_id=current_user.id)

    membership = add_group_member(
        db,
        group=group,
        entry=entry,
        child_group=child_group,
        member_role=parsed.member_role,
    )
    db.flush()
    return AppliedResource(resource_type="group_membership", resource_id=membership.id)


def apply_delete_group_member(db: Session, payload: dict[str, Any]) -> AppliedResource:
    parsed = _parse_payload(
        payload,
        change_type=AgentChangeType.DELETE_GROUP_MEMBER,
        model_type=DeleteGroupMemberPayload,
    )

    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group = _find_scoped_group_by_id(
        db,
        group_id=parsed.group_ref.group_id or "",
        current_user_id=current_user.id,
    )

    target_entry_id = _resolve_applied_entry_id(db, parsed.entry_ref) if parsed.entry_ref is not None else None
    target_child_group_id = (
        _resolve_applied_group_id(db, parsed.child_group_ref) if parsed.child_group_ref is not None else None
    )
    membership = next(
        (
            item
            for item in group.memberships
            if (target_entry_id is not None and item.entry_id == target_entry_id)
            or (target_child_group_id is not None and item.child_group_id == target_child_group_id)
        ),
        None,
    )
    if membership is None:
        raise ValueError("Group membership not found")
    membership_id = membership.id
    remove_group_member(db, group=group, membership_id=membership_id)
    db.flush()
    return AppliedResource(resource_type="group_membership", resource_id=membership_id)


APPLY_CHANGE_HANDLERS: dict[AgentChangeType, ChangeApplyHandler] = {
    AgentChangeType.CREATE_ENTRY: apply_create_entry,
    AgentChangeType.UPDATE_ENTRY: apply_update_entry,
    AgentChangeType.DELETE_ENTRY: apply_delete_entry,
    AgentChangeType.CREATE_GROUP: apply_create_group,
    AgentChangeType.UPDATE_GROUP: apply_update_group,
    AgentChangeType.DELETE_GROUP: apply_delete_group,
    AgentChangeType.CREATE_GROUP_MEMBER: apply_create_group_member,
    AgentChangeType.DELETE_GROUP_MEMBER: apply_delete_group_member,
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
