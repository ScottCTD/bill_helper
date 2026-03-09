from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry, EntryGroup, EntryGroupMember, Tag
from backend.services.agent.change_contracts import (
    ChildGroupMemberTargetPayload,
    CreateAccountPayload,
    CreateGroupMemberPayload,
    CreateGroupPayload,
    CreateEntryPayload,
    CreateEntityPayload,
    CreateTagPayload,
    DeleteAccountPayload,
    DeleteGroupMemberPayload,
    DeleteGroupPayload,
    DeleteEntryPayload,
    DeleteEntityPayload,
    DeleteTagPayload,
    ChangePayloadModel,
    EntryGroupMemberTargetPayload,
    EntryReferencePayload,
    EntrySelectorPayload,
    UpdateAccountPayload,
    UpdateGroupPayload,
    UpdateEntryPayload,
    UpdateEntityPayload,
    UpdateTagPayload,
)
from backend.services.agent.entry_references import (
    entry_public_summary,
    find_entries_by_exact_id,
    find_entries_by_selector,
)
from backend.services.agent.group_references import (
    find_groups_by_id,
    group_owner_condition,
    group_public_summary,
)
from backend.schemas_finance import EntityCreate, EntityUpdate
from backend.services.accounts import (
    AccountPatch,
    create_account_root,
    delete_account_and_entity_root,
    find_account_by_name,
    update_account_root,
)
from backend.services.crud_policy import PolicyViolation
from backend.services.entries import set_entry_tags, soft_delete_entry
from backend.services.entities import (
    create_entity_from_payload,
    delete_entity_and_preserve_labels,
    ensure_entity_by_name,
    find_entity_by_name,
    update_entity_from_payload,
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


ChangeApplyHandler = Callable[[Session, ChangePayloadModel], AppliedResource]


def _find_unique_entry_by_selector(db: Session, selector_payload: EntrySelectorPayload) -> Entry:
    matches = find_entries_by_selector(db, selector_payload)
    if not matches:
        raise ValueError("Entry selector did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry selector is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def _find_unique_entry_by_id(db: Session, entry_id: str) -> Entry:
    matches = find_entries_by_exact_id(db, entry_id)
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


def _resolve_existing_group_id(db: Session, *, group_id: str, current_user_id: str) -> str:
    matches = find_groups_by_id(db, group_id=group_id, owner_user_id=current_user_id)
    if not matches:
        raise ValueError("Group not found")
    if len(matches) > 1:
        candidates = "; ".join(group_public_summary(group) for group in matches)
        raise ValueError(f"Group id is ambiguous ({len(matches)} matches): {candidates}")
    return str(matches[0].id)


def _resolve_existing_entry_id(db: Session, *, entry_id: str) -> str:
    matches = find_entries_by_exact_id(db, entry_id)
    if not matches:
        raise ValueError("Entry id did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry id is ambiguous ({len(matches)} matches): {candidates}")
    return str(matches[0].id)


def _resolve_applied_group_id(db: Session, reference: GroupReferencePayload, *, current_user_id: str) -> str:
    if reference.group_id is not None:
        return _resolve_existing_group_id(db, group_id=reference.group_id, current_user_id=current_user_id)

    assert reference.create_group_proposal_id is not None
    item = _find_change_item_by_id(db, reference.create_group_proposal_id)
    if item.change_type != AgentChangeType.CREATE_GROUP:
        raise ValueError("Referenced proposal is not a create_group proposal")
    if item.applied_resource_type != "group" or item.applied_resource_id is None:
        raise ValueError("Referenced group proposal has not been applied yet")
    return item.applied_resource_id


def _resolve_applied_entry_id(db: Session, reference: EntryReferencePayload) -> str:
    if reference.entry_id is not None:
        return _resolve_existing_entry_id(db, entry_id=reference.entry_id)

    assert reference.create_entry_proposal_id is not None
    item = _find_change_item_by_id(db, reference.create_entry_proposal_id)
    if item.change_type != AgentChangeType.CREATE_ENTRY:
        raise ValueError("Referenced proposal is not a create_entry proposal")
    if item.applied_resource_type != "entry" or item.applied_resource_id is None:
        raise ValueError("Referenced entry proposal has not been applied yet")
    return item.applied_resource_id


def _resolve_applied_group_member_target_ids(
    db: Session,
    *,
    target: EntryGroupMemberTargetPayload | ChildGroupMemberTargetPayload,
    current_user_id: str,
) -> tuple[str | None, str | None]:
    if isinstance(target, EntryGroupMemberTargetPayload):
        return _resolve_applied_entry_id(db, target.entry_ref), None
    return None, _resolve_applied_group_id(db, target.group_ref, current_user_id=current_user_id)


def _find_scoped_group_by_id(db: Session, *, group_id: str, current_user_id: str) -> EntryGroup:
    resolved_group_id = _resolve_existing_group_id(db, group_id=group_id, current_user_id=current_user_id)
    group = db.scalar(
        select(EntryGroup)
        .where(
            EntryGroup.id == resolved_group_id,
            group_owner_condition(current_user_id),
        )
        .options(*group_tree_options())
    )
    if group is None:  # pragma: no cover - guarded by _resolve_existing_group_id
        raise ValueError("Group not found")
    return group


def apply_create_tag(db: Session, payload: CreateTagPayload) -> AppliedResource:
    existing = db.scalar(select(Tag).where(Tag.name == payload.name))
    if existing is not None:
        return AppliedResource(resource_type="tag", resource_id=str(existing.id))

    tag = Tag(name=payload.name, color=resolve_tag_color(None))
    db.add(tag)
    db.flush()
    assign_single_term_by_name(
        db,
        taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
        subject_type=TAG_TYPE_SUBJECT_TYPE,
        subject_id=tag.id,
        term_name=payload.type,
    )
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_update_tag(db: Session, payload: UpdateTagPayload) -> AppliedResource:
    tag = db.scalar(select(Tag).where(Tag.name == payload.name))
    if tag is None:
        raise ValueError("Tag not found")

    if "name" in payload.patch.model_fields_set and payload.patch.name is not None:
        existing = db.scalar(select(Tag).where(Tag.name == payload.patch.name))
        if existing is not None and existing.id != tag.id:
            raise ValueError("Tag already exists")
        tag.name = payload.patch.name

    if "type" in payload.patch.model_fields_set:
        assign_single_term_by_name(
            db,
            taxonomy_key=TAG_TYPE_TAXONOMY_KEY,
            subject_type=TAG_TYPE_SUBJECT_TYPE,
            subject_id=tag.id,
            term_name=payload.patch.type,
        )

    db.add(tag)
    db.flush()
    return AppliedResource(resource_type="tag", resource_id=str(tag.id))


def apply_delete_tag(db: Session, payload: DeleteTagPayload) -> AppliedResource:
    tag = db.scalar(select(Tag).where(Tag.name == payload.name))
    if tag is None:
        raise ValueError("Tag not found")

    resource_id = str(tag.id)
    delete_tag(db, tag=tag)
    return AppliedResource(resource_type="tag", resource_id=resource_id)


def apply_create_entity(db: Session, payload: CreateEntityPayload) -> AppliedResource:
    try:
        entity = create_entity_from_payload(
            db,
            payload=EntityCreate(name=payload.name, category=payload.category),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_update_entity(db: Session, payload: UpdateEntityPayload) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name)
    if entity is None:
        raise ValueError("Entity not found")
    try:
        update_entity_from_payload(
            db,
            entity=entity,
            payload=EntityUpdate.model_validate(payload.patch.model_dump(exclude_unset=True)),
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=entity.id)


def apply_delete_entity(db: Session, payload: DeleteEntityPayload) -> AppliedResource:
    entity = find_entity_by_name(db, payload.name)
    if entity is None:
        raise ValueError("Entity not found")

    resource_id = entity.id
    try:
        delete_entity_and_preserve_labels(db, entity=entity)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="entity", resource_id=resource_id)


def apply_create_account(db: Session, payload: CreateAccountPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    owner_user = ensure_current_user(db, settings.current_user_name)
    try:
        account = create_account_root(
            db,
            name=payload.name,
            owner_user_id=owner_user.id,
            markdown_body=payload.markdown_body,
            currency_code=payload.currency_code,
            is_active=payload.is_active,
        )
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_update_account(db: Session, payload: UpdateAccountPayload) -> AppliedResource:
    account = find_account_by_name(db, payload.name)
    if account is None:
        raise ValueError("Account not found")

    patch = AccountPatch.model_validate(payload.patch.model_dump(exclude_unset=True))
    try:
        update_account_root(db, account=account, patch=patch)
    except PolicyViolation as exc:
        raise ValueError(exc.detail) from exc
    return AppliedResource(resource_type="account", resource_id=account.id)


def apply_delete_account(db: Session, payload: DeleteAccountPayload) -> AppliedResource:
    account = find_account_by_name(db, payload.name)
    if account is None:
        raise ValueError("Account not found")

    resource_id = account.id
    delete_account_and_entity_root(db, account=account)
    return AppliedResource(resource_type="account", resource_id=resource_id)


def apply_create_entry(db: Session, payload: CreateEntryPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    currency_code = (payload.currency_code or settings.default_currency_code).strip().upper()

    from_entity = ensure_entity_by_name(db, payload.from_entity)
    to_entity = ensure_entity_by_name(db, payload.to_entity)

    owner_user = ensure_current_user(db, settings.current_user_name)

    entry = Entry(
        account_id=None,
        kind=payload.kind,
        occurred_at=payload.date,
        name=payload.name,
        amount_minor=payload.amount_minor,
        currency_code=currency_code,
        from_entity_id=from_entity.id,
        to_entity_id=to_entity.id,
        owner_user_id=owner_user.id,
        from_entity=from_entity.name,
        to_entity=to_entity.name,
        owner=owner_user.name,
        markdown_body=payload.markdown_notes,
    )
    db.add(entry)
    set_entry_tags(db, entry, payload.tags)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_update_entry(db: Session, payload: UpdateEntryPayload) -> AppliedResource:
    if payload.entry_id is not None:
        entry = _find_unique_entry_by_id(db, payload.entry_id)
    elif payload.selector is not None:
        entry = _find_unique_entry_by_selector(db, payload.selector)
    else:  # pragma: no cover - validated by Pydantic
        raise ValueError("Entry reference is required")

    if "kind" in payload.patch.model_fields_set and payload.patch.kind is not None:
        entry.kind = payload.patch.kind
    if "date" in payload.patch.model_fields_set and payload.patch.date is not None:
        entry.occurred_at = payload.patch.date
    if "name" in payload.patch.model_fields_set and payload.patch.name is not None:
        entry.name = payload.patch.name
    if "amount_minor" in payload.patch.model_fields_set and payload.patch.amount_minor is not None:
        entry.amount_minor = payload.patch.amount_minor
    if "currency_code" in payload.patch.model_fields_set and payload.patch.currency_code is not None:
        entry.currency_code = payload.patch.currency_code

    if "from_entity" in payload.patch.model_fields_set:
        if payload.patch.from_entity is None:
            entry.from_entity_id = None
            entry.from_entity = None
        else:
            from_entity = ensure_entity_by_name(db, payload.patch.from_entity)
            entry.from_entity_id = from_entity.id
            entry.from_entity = from_entity.name

    if "to_entity" in payload.patch.model_fields_set:
        if payload.patch.to_entity is None:
            entry.to_entity_id = None
            entry.to_entity = None
        else:
            to_entity = ensure_entity_by_name(db, payload.patch.to_entity)
            entry.to_entity_id = to_entity.id
            entry.to_entity = to_entity.name

    if "markdown_notes" in payload.patch.model_fields_set:
        entry.markdown_body = payload.patch.markdown_notes

    if "tags" in payload.patch.model_fields_set:
        set_entry_tags(db, entry, payload.patch.tags or [])

    db.add(entry)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_delete_entry(db: Session, payload: DeleteEntryPayload) -> AppliedResource:
    if payload.entry_id is not None:
        entry = _find_unique_entry_by_id(db, payload.entry_id)
    elif payload.selector is not None:
        entry = _find_unique_entry_by_selector(db, payload.selector)
    else:  # pragma: no cover - validated by Pydantic
        raise ValueError("Entry reference is required")
    soft_delete_entry(db, entry)
    db.flush()
    return AppliedResource(resource_type="entry", resource_id=entry.id)


def apply_create_group(db: Session, payload: CreateGroupPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    owner_user = ensure_current_user(db, settings.current_user_name)
    group = create_group(
        db,
        name=payload.name,
        group_type=payload.group_type,
        owner_user_id=owner_user.id,
    )
    db.flush()
    return AppliedResource(resource_type="group", resource_id=group.id)


def apply_update_group(db: Session, payload: UpdateGroupPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group = _find_scoped_group_by_id(db, group_id=payload.group_id, current_user_id=current_user.id)
    updated = rename_group(db, group=group, name=payload.patch.name or group.name)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=updated.id)


def apply_delete_group(db: Session, payload: DeleteGroupPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group = _find_scoped_group_by_id(db, group_id=payload.group_id, current_user_id=current_user.id)
    resource_id = group.id
    delete_group(db, group=group)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=resource_id)


def apply_create_group_member(db: Session, payload: CreateGroupMemberPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group_id = _resolve_applied_group_id(db, payload.group_ref, current_user_id=current_user.id)
    group = _find_scoped_group_by_id(db, group_id=group_id, current_user_id=current_user.id)

    entry = None
    child_group = None
    target_entry_id, target_child_group_id = _resolve_applied_group_member_target_ids(
        db,
        target=payload.target,
        current_user_id=current_user.id,
    )
    if target_entry_id is not None:
        entry_id = target_entry_id
        entry = _find_unique_entry_by_id(db, entry_id)
    if target_child_group_id is not None:
        child_group_id = target_child_group_id
        child_group = _find_scoped_group_by_id(db, group_id=child_group_id, current_user_id=current_user.id)

    membership = add_group_member(
        db,
        group=group,
        entry=entry,
        child_group=child_group,
        member_role=payload.member_role,
    )
    db.flush()
    return AppliedResource(resource_type="group_membership", resource_id=membership.id)


def apply_delete_group_member(db: Session, payload: DeleteGroupMemberPayload) -> AppliedResource:
    settings = resolve_runtime_settings(db)
    current_user = ensure_current_user(db, settings.current_user_name)
    group = _find_scoped_group_by_id(
        db,
        group_id=payload.group_ref.group_id or "",
        current_user_id=current_user.id,
    )

    target_entry_id, target_child_group_id = _resolve_applied_group_member_target_ids(
        db,
        target=payload.target,
        current_user_id=current_user.id,
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
    AgentChangeType.CREATE_ACCOUNT: apply_create_account,
    AgentChangeType.UPDATE_ACCOUNT: apply_update_account,
    AgentChangeType.DELETE_ACCOUNT: apply_delete_account,
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


def apply_change_item_payload(
    db: Session,
    *,
    change_type: AgentChangeType,
    payload: ChangePayloadModel,
) -> AppliedResource:
    handler = APPLY_CHANGE_HANDLERS.get(change_type)
    if handler is None:  # pragma: no cover - enum guard
        raise ValueError(f"Unsupported change type: {change_type}")
    return handler(db, payload)
