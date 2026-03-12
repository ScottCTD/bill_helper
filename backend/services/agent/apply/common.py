from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.enums_agent import AgentChangeType
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry, EntryGroup
from backend.services.agent.change_contracts import ChangePayloadModel
from backend.services.agent.change_contracts.entries import EntryReferencePayload, EntrySelectorPayload
from backend.services.agent.change_contracts.groups import (
    ChildGroupMemberTargetPayload,
    EntryGroupMemberTargetPayload,
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


@dataclass(frozen=True, slots=True)
class AppliedResource:
    resource_type: str
    resource_id: str


ChangeApplyHandler = Callable[[Session, ChangePayloadModel, RequestPrincipal], AppliedResource]


def find_unique_entry_by_selector(
    db: Session,
    selector_payload: EntrySelectorPayload,
    *,
    principal: RequestPrincipal,
) -> Entry:
    matches = find_entries_by_selector(
        db,
        selector_payload,
        principal_user_id=principal.user_id,
        is_admin=False,
    )
    if not matches:
        raise ValueError("Entry selector did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry selector is ambiguous ({len(matches)} matches): {candidates}")
    return matches[0]


def find_unique_entry_by_id(
    db: Session,
    entry_id: str,
    *,
    principal: RequestPrincipal,
) -> Entry:
    matches = find_entries_by_exact_id(
        db,
        entry_id,
        principal_user_id=principal.user_id,
        is_admin=False,
    )
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


def resolve_existing_group_id(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
) -> str:
    matches = find_groups_by_id(db, group_id=group_id, owner_user_id=principal.user_id)
    if not matches:
        raise ValueError("Group not found")
    if len(matches) > 1:
        candidates = "; ".join(group_public_summary(group) for group in matches)
        raise ValueError(f"Group id is ambiguous ({len(matches)} matches): {candidates}")
    return str(matches[0].id)


def resolve_existing_entry_id(
    db: Session,
    *,
    entry_id: str,
    principal: RequestPrincipal,
) -> str:
    matches = find_entries_by_exact_id(
        db,
        entry_id,
        principal_user_id=principal.user_id,
        is_admin=False,
    )
    if not matches:
        raise ValueError("Entry id did not match any entry")
    if len(matches) > 1:
        candidates = "; ".join(entry_public_summary(entry) for entry in matches)
        raise ValueError(f"Entry id is ambiguous ({len(matches)} matches): {candidates}")
    return str(matches[0].id)


def resolve_applied_group_id(
    db: Session,
    reference: GroupReferencePayload,
    *,
    principal: RequestPrincipal,
) -> str:
    if reference.group_id is not None:
        return resolve_existing_group_id(db, group_id=reference.group_id, principal=principal)

    assert reference.create_group_proposal_id is not None
    item = find_change_item_by_id(db, reference.create_group_proposal_id)
    if item.change_type != AgentChangeType.CREATE_GROUP:
        raise ValueError("Referenced proposal is not a create_group proposal")
    if item.applied_resource_type != "group" or item.applied_resource_id is None:
        raise ValueError("Referenced group proposal has not been applied yet")
    return item.applied_resource_id


def resolve_applied_entry_id(
    db: Session,
    reference: EntryReferencePayload,
    *,
    principal: RequestPrincipal,
) -> str:
    if reference.entry_id is not None:
        return resolve_existing_entry_id(db, entry_id=reference.entry_id, principal=principal)

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
    principal: RequestPrincipal,
) -> tuple[str | None, str | None]:
    if isinstance(target, EntryGroupMemberTargetPayload):
        return resolve_applied_entry_id(db, target.entry_ref, principal=principal), None
    return None, resolve_applied_group_id(db, target.group_ref, principal=principal)


def find_scoped_group_by_id(
    db: Session,
    *,
    group_id: str,
    principal: RequestPrincipal,
) -> EntryGroup:
    resolved_group_id = resolve_existing_group_id(db, group_id=group_id, principal=principal)
    group = db.scalar(
        select(EntryGroup)
        .where(
            EntryGroup.id == resolved_group_id,
            group_owner_condition(principal.user_id),
        )
        .options(*group_tree_options())
    )
    if group is None:  # pragma: no cover - guarded by resolve_existing_group_id
        raise ValueError("Group not found")
    return group
