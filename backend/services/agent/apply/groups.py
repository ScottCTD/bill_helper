from __future__ import annotations

from sqlalchemy.orm import Session

from backend.services.agent.apply.common import (
    AppliedResource,
    find_scoped_group_by_id,
    find_unique_entry_by_id,
    resolve_applied_group_id,
    resolve_applied_group_member_target_ids,
    resolve_current_user,
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
    rename_group,
)


def apply_create_group(db: Session, payload: CreateGroupPayload) -> AppliedResource:
    current_user = resolve_current_user(db)
    group = create_group(
        db,
        name=payload.name,
        group_type=payload.group_type,
        owner_user_id=current_user.id,
    )
    db.flush()
    return AppliedResource(resource_type="group", resource_id=group.id)


def apply_update_group(db: Session, payload: UpdateGroupPayload) -> AppliedResource:
    current_user = resolve_current_user(db)
    group = find_scoped_group_by_id(db, group_id=payload.group_id, current_user_id=current_user.id)
    updated = rename_group(db, group=group, name=payload.patch.name or group.name)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=updated.id)


def apply_delete_group(db: Session, payload: DeleteGroupPayload) -> AppliedResource:
    current_user = resolve_current_user(db)
    group = find_scoped_group_by_id(db, group_id=payload.group_id, current_user_id=current_user.id)
    resource_id = group.id
    delete_group(db, group=group)
    db.flush()
    return AppliedResource(resource_type="group", resource_id=resource_id)


def apply_create_group_member(db: Session, payload: CreateGroupMemberPayload) -> AppliedResource:
    current_user = resolve_current_user(db)
    group_id = resolve_applied_group_id(db, payload.group_ref, current_user_id=current_user.id)
    group = find_scoped_group_by_id(db, group_id=group_id, current_user_id=current_user.id)

    entry = None
    child_group = None
    target_entry_id, target_child_group_id = resolve_applied_group_member_target_ids(
        db,
        target=payload.target,
        current_user_id=current_user.id,
    )
    if target_entry_id is not None:
        entry = find_unique_entry_by_id(db, target_entry_id)
    if target_child_group_id is not None:
        child_group = find_scoped_group_by_id(db, group_id=target_child_group_id, current_user_id=current_user.id)

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
    current_user = resolve_current_user(db)
    group = find_scoped_group_by_id(
        db,
        group_id=payload.group_ref.group_id or "",
        current_user_id=current_user.id,
    )

    target_entry_id, target_child_group_id = resolve_applied_group_member_target_ids(
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
