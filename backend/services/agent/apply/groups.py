# CALLING SPEC:
# - Purpose: implement focused service logic for `groups`.
# - Inputs: callers that import `backend/services/agent/apply/groups.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `groups`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from sqlalchemy.orm import Session

from backend.auth.contracts import RequestPrincipal
from backend.contracts_groups import (
    ChildGroupMemberTarget,
    EntryGroupMemberTarget,
    GroupCreateCommand,
    GroupMemberCreateCommand,
    GroupPatch,
)
from backend.services.agent.apply.common import (
    AppliedResource,
    find_scoped_group_by_id,
    find_unique_entry_by_id,
    resolve_applied_group_id,
    resolve_applied_group_member_target_ids,
)
from backend.services.agent.change_contracts.groups import (
    CreateGroupMemberPayload,
    CreateGroupPayload,
    DeleteGroupMemberPayload,
    DeleteGroupPayload,
    UpdateGroupPayload,
)
from backend.services.groups import (
    add_group_member,
    create_group,
    delete_group,
    remove_group_member,
    update_group,
)


def apply_create_group(
    db: Session,
    payload: CreateGroupPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    group = create_group(
        db,
        command=GroupCreateCommand(name=payload.name, group_type=payload.group_type),
        owner_user_id=principal.user_id,
    )
    db.flush()
    return AppliedResource(resource_type="group", resource_id=group.id)


def apply_update_group(
    db: Session,
    payload: UpdateGroupPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    group = find_scoped_group_by_id(db, group_id=payload.group_id, principal=principal)
    updated = update_group(
        db,
        group=group,
        patch=GroupPatch.model_validate(payload.patch.model_dump(exclude_unset=True)),
    )
    db.flush()
    return AppliedResource(resource_type="group", resource_id=updated.id)


def apply_delete_group(
    db: Session,
    payload: DeleteGroupPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    group = find_scoped_group_by_id(db, group_id=payload.group_id, principal=principal)
    resource_id = group.id
    delete_group(db, group=group)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=resource_id)


def apply_create_group_member(
    db: Session,
    payload: CreateGroupMemberPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    group_id = resolve_applied_group_id(db, payload.group_ref, principal=principal)
    group = find_scoped_group_by_id(db, group_id=group_id, principal=principal)

    target_entry_id, target_child_group_id = resolve_applied_group_member_target_ids(
        db,
        target=payload.target,
        principal=principal,
    )
    if target_entry_id is not None:
        entry = find_unique_entry_by_id(db, target_entry_id, principal=principal)
        command = GroupMemberCreateCommand(
            target=EntryGroupMemberTarget(entry_id=entry.id),
            member_role=payload.member_role,
        )
    else:
        child_group = find_scoped_group_by_id(db, group_id=target_child_group_id, principal=principal)
        command = GroupMemberCreateCommand(
            target=ChildGroupMemberTarget(group_id=child_group.id),
            member_role=payload.member_role,
        )

    membership = add_group_member(db, group=group, command=command)
    db.flush()
    return AppliedResource(resource_type="group_membership", resource_id=membership.id)


def apply_delete_group_member(
    db: Session,
    payload: DeleteGroupMemberPayload,
    principal: RequestPrincipal,
) -> AppliedResource:
    group = find_scoped_group_by_id(db, group_id=payload.group_ref.group_id or "", principal=principal)

    target_entry_id, target_child_group_id = resolve_applied_group_member_target_ids(
        db,
        target=payload.target,
        principal=principal,
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
