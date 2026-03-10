from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.contracts_groups import (
    ChildGroupMemberTarget,
    EntryGroupMemberTarget,
    GroupCreateCommand,
    GroupMemberCreateCommand,
    GroupPatch,
)
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
from backend.models_finance import Entry, EntryGroup, EntryGroupMember
from backend.schemas_finance import GroupEdge, GroupGraphRead, GroupNode, GroupSummaryRead


def entry_group_options():
    return (
        selectinload(Entry.group_membership)
        .selectinload(EntryGroupMember.group)
        .selectinload(EntryGroup.parent_membership)
        .selectinload(EntryGroupMember.group),
    )


def group_tree_options():
    memberships = selectinload(EntryGroup.memberships)
    return (
        selectinload(EntryGroup.parent_membership).selectinload(EntryGroupMember.group),
        memberships.selectinload(EntryGroupMember.entry),
        memberships.selectinload(EntryGroupMember.child_group)
        .selectinload(EntryGroup.memberships)
        .selectinload(EntryGroupMember.entry),
    )


def load_group_tree(db: Session, group_id: str) -> EntryGroup | None:
    return db.scalar(
        select(EntryGroup)
        .execution_options(populate_existing=True)
        .options(*group_tree_options())
        .where(EntryGroup.id == group_id)
    )


def create_group(
    db: Session,
    *,
    command: GroupCreateCommand,
    owner_user_id: str,
) -> EntryGroup:
    group = EntryGroup(
        owner_user_id=owner_user_id,
        name=command.name,
        group_type=command.group_type,
    )
    db.add(group)
    db.flush()
    loaded = load_group_tree(db, group.id)
    if loaded is None:  # pragma: no cover - post-flush invariant
        raise ValueError("Failed to load created group.")
    return loaded


def update_group(
    db: Session,
    *,
    group: EntryGroup,
    patch: GroupPatch,
) -> EntryGroup:
    if "name" in patch.model_fields_set and patch.name is not None:
        group.name = patch.name
    db.add(group)
    db.flush()
    loaded = load_group_tree(db, group.id)
    if loaded is None:  # pragma: no cover - post-flush invariant
        raise ValueError("Failed to load renamed group.")
    return loaded


def delete_group(db: Session, *, group: EntryGroup) -> None:
    if group.parent_membership is not None:
        raise ValueError("Remove this group from its parent before deleting it.")
    if group.memberships:
        raise ValueError("Remove all direct members before deleting this group.")
    db.delete(group)
    db.flush()


def add_group_member(
    db: Session,
    *,
    group: EntryGroup,
    command: GroupMemberCreateCommand,
) -> EntryGroupMember:
    entry, child_group = _resolve_member_target(db, target=command.target)
    _validate_member_target(
        db,
        group=group,
        entry=entry,
        child_group=child_group,
        member_role=command.member_role,
    )

    member = EntryGroupMember(
        group_id=group.id,
        entry_id=entry.id if entry is not None else None,
        child_group_id=child_group.id if child_group is not None else None,
        member_role=command.member_role,
        position=_next_member_position(group),
    )
    db.add(member)
    db.flush()
    db.expire_all()

    loaded_group = load_group_tree(db, group.id)
    if loaded_group is None:  # pragma: no cover - post-flush invariant
        raise ValueError("Failed to load group after membership update.")
    validate_group_integrity(loaded_group)

    if loaded_group.parent_membership is not None:
        loaded_parent = load_group_tree(db, loaded_group.parent_membership.group_id)
        if loaded_parent is not None:
            validate_group_integrity(loaded_parent)

    loaded_member = db.get(EntryGroupMember, member.id)
    if loaded_member is None:  # pragma: no cover - post-flush invariant
        raise ValueError("Failed to load created membership.")
    return loaded_member


def remove_group_member(
    db: Session,
    *,
    group: EntryGroup,
    membership_id: str,
) -> None:
    membership = db.scalar(
        select(EntryGroupMember).where(
            EntryGroupMember.id == membership_id,
            EntryGroupMember.group_id == group.id,
        )
    )
    if membership is None:
        raise ValueError("Group membership not found.")
    db.delete(membership)
    db.flush()


def set_entry_direct_group(
    db: Session,
    *,
    entry: Entry,
    group: EntryGroup | None,
    member_role: GroupMemberRole | None = None,
) -> None:
    if group is None and member_role is not None:
        raise ValueError("direct_group_member_role requires a direct group.")

    existing_membership = entry.group_membership
    if existing_membership is not None:
        current_group_id = existing_membership.group_id
        current_role = existing_membership.member_role
        if group is not None and current_group_id == group.id and current_role == member_role:
            return
        entry.group_membership = None
        db.delete(existing_membership)
        db.flush()

    if group is None:
        return

    add_group_member(
        db,
        group=group,
        command=GroupMemberCreateCommand(
            target=EntryGroupMemberTarget(entry_id=entry.id),
            member_role=member_role,
        ),
    )


def build_group_summary(group: EntryGroup) -> GroupSummaryRead:
    direct_members = _sorted_memberships(group)
    descendant_entries = _descendant_entries_for_group(group)
    first_occurred_at = min((entry.occurred_at for entry in descendant_entries), default=None)
    last_occurred_at = max((entry.occurred_at for entry in descendant_entries), default=None)
    direct_entry_count = sum(1 for membership in direct_members if membership.entry_id is not None)
    direct_child_group_count = sum(1 for membership in direct_members if membership.child_group_id is not None)
    return GroupSummaryRead(
        id=group.id,
        name=group.name,
        group_type=group.group_type,
        parent_group_id=group.parent_membership.group_id if group.parent_membership is not None else None,
        direct_member_count=len(direct_members),
        direct_entry_count=direct_entry_count,
        direct_child_group_count=direct_child_group_count,
        descendant_entry_count=len(descendant_entries),
        first_occurred_at=first_occurred_at,
        last_occurred_at=last_occurred_at,
    )


def build_group_graph(group: EntryGroup) -> GroupGraphRead:
    direct_members = _sorted_memberships(group)
    summary = build_group_summary(group)
    nodes = [_membership_to_node(membership) for membership in direct_members]
    edges = _build_group_edges(group.group_type, direct_members)
    return GroupGraphRead(
        id=group.id,
        name=group.name,
        group_type=group.group_type,
        parent_group_id=summary.parent_group_id,
        direct_member_count=summary.direct_member_count,
        direct_entry_count=summary.direct_entry_count,
        direct_child_group_count=summary.direct_child_group_count,
        descendant_entry_count=summary.descendant_entry_count,
        first_occurred_at=summary.first_occurred_at,
        last_occurred_at=summary.last_occurred_at,
        nodes=nodes,
        edges=edges,
    )


def validate_group_integrity(group: EntryGroup) -> None:
    direct_members = _sorted_memberships(group)

    if group.parent_membership is not None and any(member.child_group_id is not None for member in direct_members):
        raise ValueError("Nested groups cannot contain child groups.")

    for member in direct_members:
        if member.child_group is None:
            continue
        nested_members = _sorted_memberships(member.child_group)
        if any(nested_member.child_group_id is not None for nested_member in nested_members):
            raise ValueError("Nesting depth cannot exceed one level.")

    if group.group_type == GroupType.BUNDLE:
        if any(member.member_role is not None for member in direct_members):
            raise ValueError("Bundle groups do not accept member roles.")
        return

    if group.group_type == GroupType.SPLIT:
        parents = [member for member in direct_members if member.member_role == GroupMemberRole.PARENT]
        if len(parents) > 1:
            raise ValueError("Split groups can have at most one parent member.")

        for member in direct_members:
            if member.member_role is None:
                raise ValueError("Split groups require a role for every direct member.")
            expected_kind = (
                EntryKind.EXPENSE
                if member.member_role == GroupMemberRole.PARENT
                else EntryKind.INCOME
            )
            for entry in _descendant_entries_for_membership(member):
                if entry.kind != expected_kind:
                    raise ValueError(
                        "Split group descendants must be EXPENSE under the parent and INCOME under children."
                    )
        return

    if any(member.member_role is not None for member in direct_members):
        raise ValueError("Recurring groups do not accept member roles.")

    descendant_kinds = {entry.kind for entry in _descendant_entries_for_group(group)}
    if len(descendant_kinds) > 1:
        raise ValueError("Recurring groups require all descendant entries to share the same kind.")


def _validate_member_target(
    db: Session,
    *,
    group: EntryGroup,
    entry: Entry | None,
    child_group: EntryGroup | None,
    member_role: GroupMemberRole | None,
) -> None:
    if group.group_type == GroupType.SPLIT:
        if member_role is None:
            raise ValueError("Split groups require a member role.")
    elif member_role is not None:
        raise ValueError("Only split groups accept member roles.")

    if entry is not None:
        if entry.is_deleted:
            raise ValueError("Cannot add a deleted entry to a group.")
        existing_entry_membership = db.scalar(
            select(EntryGroupMember).where(EntryGroupMember.entry_id == entry.id)
        )
        if existing_entry_membership is not None:
            raise ValueError("This entry already belongs to a group.")
        return

    assert child_group is not None  # narrowed by caller
    if child_group.id == group.id:
        raise ValueError("A group cannot contain itself.")
    if group.parent_membership is not None:
        raise ValueError("Nested groups cannot contain child groups.")

    existing_child_membership = db.scalar(
        select(EntryGroupMember).where(EntryGroupMember.child_group_id == child_group.id)
    )
    if existing_child_membership is not None:
        raise ValueError("This child group already belongs to a parent group.")

    if any(member.child_group_id is not None for member in _sorted_memberships(child_group)):
        raise ValueError("Child groups cannot themselves contain child groups.")


def _resolve_member_target(
    db: Session,
    *,
    target: EntryGroupMemberTarget | ChildGroupMemberTarget,
) -> tuple[Entry | None, EntryGroup | None]:
    if isinstance(target, EntryGroupMemberTarget):
        entry = db.get(Entry, target.entry_id)
        if entry is None:
            raise ValueError("Entry not found.")
        return entry, None

    child_group = db.get(EntryGroup, target.group_id)
    if child_group is None:
        raise ValueError("Child group not found.")
    return None, child_group


def _next_member_position(group: EntryGroup) -> int:
    if not group.memberships:
        return 0
    return max(member.position for member in group.memberships) + 1


def _sorted_memberships(group: EntryGroup) -> list[EntryGroupMember]:
    return sorted(
        group.memberships,
        key=lambda member: (member.position, member.created_at, member.id),
    )


def _descendant_entries_for_group(group: EntryGroup) -> list[Entry]:
    entries: list[Entry] = []
    for membership in _sorted_memberships(group):
        entries.extend(_descendant_entries_for_membership(membership))
    return entries


def _descendant_entries_for_membership(membership: EntryGroupMember) -> list[Entry]:
    if membership.entry is not None:
        return [] if membership.entry.is_deleted else [membership.entry]

    if membership.child_group is None:
        return []

    return [
        child_membership.entry
        for child_membership in _sorted_memberships(membership.child_group)
        if child_membership.entry is not None and not child_membership.entry.is_deleted
    ]


def _membership_representative_date(membership: EntryGroupMember) -> date | None:
    descendant_entries = _descendant_entries_for_membership(membership)
    if not descendant_entries:
        return None
    return min(entry.occurred_at for entry in descendant_entries)


def _membership_graph_id(membership: EntryGroupMember) -> str:
    return f"member-{membership.id}"


def _membership_to_node(membership: EntryGroupMember) -> GroupNode:
    representative_occurred_at = _membership_representative_date(membership)
    if membership.entry is not None:
        entry = membership.entry
        return GroupNode(
            graph_id=_membership_graph_id(membership),
            membership_id=membership.id,
            subject_id=entry.id,
            node_type="ENTRY",
            name=entry.name,
            member_role=membership.member_role,
            representative_occurred_at=representative_occurred_at,
            kind=entry.kind,
            amount_minor=entry.amount_minor,
            currency_code=entry.currency_code,
            occurred_at=entry.occurred_at,
        )

    child_group = membership.child_group
    if child_group is None:  # pragma: no cover - schema invariant
        raise ValueError("Group membership is missing its target.")

    descendant_entries = _descendant_entries_for_group(child_group)
    return GroupNode(
        graph_id=_membership_graph_id(membership),
        membership_id=membership.id,
        subject_id=child_group.id,
        node_type="GROUP",
        name=child_group.name,
        member_role=membership.member_role,
        representative_occurred_at=representative_occurred_at,
        group_type=child_group.group_type,
        descendant_entry_count=len(descendant_entries),
        first_occurred_at=min((entry.occurred_at for entry in descendant_entries), default=None),
        last_occurred_at=max((entry.occurred_at for entry in descendant_entries), default=None),
    )


def _build_group_edges(group_type: GroupType, memberships: list[EntryGroupMember]) -> list[GroupEdge]:
    if len(memberships) < 2:
        return []

    if group_type == GroupType.BUNDLE:
        edges: list[GroupEdge] = []
        for source_index, source in enumerate(memberships):
            for target in memberships[source_index + 1 :]:
                edges.append(
                    GroupEdge(
                        id=f"edge-{source.id}-{target.id}",
                        source_graph_id=_membership_graph_id(source),
                        target_graph_id=_membership_graph_id(target),
                        group_type=group_type,
                    )
                )
        return edges

    if group_type == GroupType.SPLIT:
        parent_member = next(
            (member for member in memberships if member.member_role == GroupMemberRole.PARENT),
            None,
        )
        if parent_member is None:
            return []
        return [
            GroupEdge(
                id=f"edge-{parent_member.id}-{child.id}",
                source_graph_id=_membership_graph_id(parent_member),
                target_graph_id=_membership_graph_id(child),
                group_type=group_type,
            )
            for child in memberships
            if child.id != parent_member.id
        ]

    sorted_memberships = sorted(
        memberships,
        key=lambda member: (
            _membership_representative_date(member) is None,
            _membership_representative_date(member) or date.max,
            member.position,
            member.created_at,
            member.id,
        ),
    )
    return [
        GroupEdge(
            id=f"edge-{left.id}-{right.id}",
            source_graph_id=_membership_graph_id(left),
            target_graph_id=_membership_graph_id(right),
            group_type=group_type,
        )
        for left, right in zip(sorted_memberships, sorted_memberships[1:], strict=False)
    ]
