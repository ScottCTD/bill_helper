from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry, EntryGroup
from backend.services.agent.change_contracts import (
    ChangePayloadModel,
    ChildGroupMemberTargetPayload,
    EntryGroupMemberTargetPayload,
    EntryReferencePayload,
    EntrySelectorPayload,
    GroupReferencePayload,
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
from backend.services.groups import group_tree_options
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.users import ensure_current_user


@dataclass(frozen=True, slots=True)
class AppliedResource:
    resource_type: str
    resource_id: str


ChangeApplyHandler = Callable[[Session, ChangePayloadModel], AppliedResource]


def find_unique_entry_by_selector(db: Session, selector_payload: EntrySelectorPayload) -> Entry:
    matches = find_entries_by_selector(db, selector_payload)
    if not matches:
        raise ValueError("Entry selector did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry selector is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def find_unique_entry_by_id(db: Session, entry_id: str) -> Entry:
    matches = find_entries_by_exact_id(db, entry_id)
    if not matches:
        raise ValueError("Entry id did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry.id for entry in matches)
        raise ValueError(f"Entry id is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def find_change_item_by_id(db: Session, change_item_id: str) -> AgentChangeItem:
    item = db.get(AgentChangeItem, change_item_id)
    if item is None:
        raise ValueError(f"Referenced proposal not found: {change_item_id}")
    return item


def resolve_existing_group_id(db: Session, *, group_id: str, current_user_id: str) -> str:
    matches = find_groups_by_id(db, group_id=group_id, owner_user_id=current_user_id)
    if not matches:
        raise ValueError("Group not found")
    if len(matches) > 1:
        candidates = "; ".join(group_public_summary(group) for group in matches)
        raise ValueError(f"Group id is ambiguous ({len(matches)} matches): {candidates}")
    return str(matches[0].id)


def resolve_existing_entry_id(db: Session, *, entry_id: str) -> str:
    matches = find_entries_by_exact_id(db, entry_id)
    if not matches:
        raise ValueError("Entry id did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry id is ambiguous ({len(matches)} matches): {candidates}")
    return str(matches[0].id)


def resolve_applied_group_id(db: Session, reference: GroupReferencePayload, *, current_user_id: str) -> str:
    if reference.group_id is not None:
        return resolve_existing_group_id(db, group_id=reference.group_id, current_user_id=current_user_id)

    assert reference.create_group_proposal_id is not None
    item = find_change_item_by_id(db, reference.create_group_proposal_id)
    if item.change_type != AgentChangeType.CREATE_GROUP:
        raise ValueError("Referenced proposal is not a create_group proposal")
    if item.applied_resource_type != "group" or item.applied_resource_id is None:
        raise ValueError("Referenced group proposal has not been applied yet")
    return item.applied_resource_id


def resolve_applied_entry_id(db: Session, reference: EntryReferencePayload) -> str:
    if reference.entry_id is not None:
        return resolve_existing_entry_id(db, entry_id=reference.entry_id)

    assert reference.create_entry_proposal_id is not None
    item = find_change_item_by_id(db, reference.create_entry_proposal_id)
    if item.change_type != AgentChangeType.CREATE_ENTRY:
        raise ValueError("Referenced proposal is not a create_entry proposal")
    if item.applied_resource_type != "entry" or item.applied_resource_id is None:
        raise ValueError("Referenced entry proposal has not been applied yet")
    return item.applied_resource_id


def resolve_applied_group_member_target_ids(
    db: Session,
    *,
    target: EntryGroupMemberTargetPayload | ChildGroupMemberTargetPayload,
    current_user_id: str,
) -> tuple[str | None, str | None]:
    if isinstance(target, EntryGroupMemberTargetPayload):
        return resolve_applied_entry_id(db, target.entry_ref), None
    return None, resolve_applied_group_id(db, target.group_ref, current_user_id=current_user_id)


def find_scoped_group_by_id(db: Session, *, group_id: str, current_user_id: str) -> EntryGroup:
    resolved_group_id = resolve_existing_group_id(db, group_id=group_id, current_user_id=current_user_id)
    group = db.scalar(
        select(EntryGroup)
        .where(
            EntryGroup.id == resolved_group_id,
            group_owner_condition(current_user_id),
        )
        .options(*group_tree_options())
    )
    if group is None:  # pragma: no cover - guarded by resolve_existing_group_id
        raise ValueError("Group not found")
    return group


def resolve_current_user(db: Session):
    settings = resolve_runtime_settings(db)
    return ensure_current_user(db, settings.current_user_name)
