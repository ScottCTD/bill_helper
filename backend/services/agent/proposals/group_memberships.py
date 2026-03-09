from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
from backend.models_agent import AgentChangeItem
from backend.models_finance import Entry, EntryGroup
from backend.services.agent.change_contracts import (
    ChildGroupMemberTargetPayload,
    CreateGroupMemberPayload,
    DeleteGroupMemberPayload,
    EntryGroupMemberTargetPayload,
    EntryReferencePayload,
    GroupMemberTargetPayload,
    GroupReferencePayload,
    normalize_group_member_payload,
    parse_group_member_target_payload,
)
from backend.services.agent.entry_references import (
    entry_id_ambiguity_details,
    entry_to_public_record,
    find_entries_by_public_id_prefix,
)
from backend.services.agent.proposals.common import (
    create_change_item,
    pending_proposals_for_thread,
    proposal_result,
    proposal_short_id,
)
from backend.services.agent.proposals.entries import (
    entry_preview_from_proposal,
    match_existing_entry_or_error,
    resolve_entry_proposal_reference_or_error,
)
from backend.services.agent.proposals.groups import (
    canonical_group_ref_payload,
    descendant_entries_for_group,
    group_preview_from_existing,
    group_preview_from_proposal,
    group_ref_signature,
    match_existing_group_or_error,
    resolve_group_proposal_reference_or_error,
    resolved_group_type_from_ref,
    sorted_group_memberships,
)
from backend.services.agent.tool_args import ProposeUpdateGroupMembershipArgs
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult


def _canonical_entry_ref_payload(
    context: ToolContext,
    *,
    entry_ref: EntryReferencePayload,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> tuple[dict[str, Any], Entry | None, AgentChangeItem | None] | ToolExecutionResult:
    if entry_ref.entry_id is not None:
        entry = match_existing_entry_or_error(context, entry_id=entry_ref.entry_id)
        if isinstance(entry, ToolExecutionResult):
            return entry
        return {"entry_id": entry.id}, entry, None

    assert entry_ref.create_entry_proposal_id is not None
    proposal = resolve_entry_proposal_reference_or_error(
        context,
        proposal_id=entry_ref.create_entry_proposal_id,
        expected_statuses=expected_statuses,
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return {"create_entry_proposal_id": proposal.id}, None, proposal


def _canonical_group_member_target_payload(
    context: ToolContext,
    *,
    target: GroupMemberTargetPayload,
    expected_statuses: set[AgentChangeStatus] | None = None,
) -> tuple[dict[str, Any], Entry | EntryGroup | None, AgentChangeItem | None] | ToolExecutionResult:
    if isinstance(target, EntryGroupMemberTargetPayload):
        resolved_entry_ref = _canonical_entry_ref_payload(
            context,
            entry_ref=target.entry_ref,
            expected_statuses=expected_statuses,
        )
        if isinstance(resolved_entry_ref, ToolExecutionResult):
            return resolved_entry_ref
        return {"target_type": "entry", "entry_ref": resolved_entry_ref[0]}, resolved_entry_ref[1], resolved_entry_ref[2]

    resolved_group_ref = canonical_group_ref_payload(
        context,
        group_ref=target.group_ref,
        expected_statuses=expected_statuses,
    )
    if isinstance(resolved_group_ref, ToolExecutionResult):
        return resolved_group_ref
    return {"target_type": "child_group", "group_ref": resolved_group_ref[0]}, resolved_group_ref[1], resolved_group_ref[2]


def _resolved_group_member_target_preview(
    context: ToolContext,
    *,
    target: GroupMemberTargetPayload,
    enforce_add_membership_rules: bool = True,
) -> tuple[dict[str, Any], EntryKind | None] | ToolExecutionResult:
    if isinstance(target, EntryGroupMemberTargetPayload):
        if target.entry_ref.entry_id is not None:
            matches = find_entries_by_public_id_prefix(context.db, target.entry_ref.entry_id)
            if not matches:
                return error_result("no entry matched entry_id", details={"entry_id": target.entry_ref.entry_id})
            if len(matches) > 1:
                return error_result(
                    "ambiguous entry_id matched multiple entries; retry with one of the candidate ids",
                    details=entry_id_ambiguity_details(matches, entry_id=target.entry_ref.entry_id),
                )
            entry = matches[0]
            if enforce_add_membership_rules and entry.group_membership is not None:
                return error_result("this entry already belongs to a group")
            preview = entry_to_public_record(entry)
            preview["source"] = "entry"
            return preview, entry.kind

        proposal = resolve_entry_proposal_reference_or_error(
            context,
            proposal_id=target.entry_ref.create_entry_proposal_id or "",
            expected_statuses={
                AgentChangeStatus.PENDING_REVIEW,
                AgentChangeStatus.APPROVED,
                AgentChangeStatus.APPLIED,
            },
        )
        if isinstance(proposal, ToolExecutionResult):
            return proposal
        preview = entry_preview_from_proposal(proposal)
        raw_kind = proposal.payload_json.get("kind")
        entry_kind = EntryKind(str(raw_kind)) if isinstance(raw_kind, str) else None
        return preview, entry_kind

    if target.group_ref.group_id is not None:
        group = match_existing_group_or_error(context, group_id=target.group_ref.group_id)
        if isinstance(group, ToolExecutionResult):
            return group
        if enforce_add_membership_rules and group.parent_membership is not None:
            return error_result("this child group already belongs to a parent group")
        if enforce_add_membership_rules and any(
            membership.child_group_id is not None for membership in sorted_group_memberships(group)
        ):
            return error_result("child groups cannot themselves contain child groups")
        descendant_entries = descendant_entries_for_group(group)
        preview = group_preview_from_existing(group)
        preview["descendant_kinds"] = sorted({entry.kind.value for entry in descendant_entries})
        if len({entry.kind for entry in descendant_entries}) == 1 and descendant_entries:
            return preview, descendant_entries[0].kind
        return preview, None

    proposal = resolve_group_proposal_reference_or_error(
        context,
        proposal_id=target.group_ref.create_group_proposal_id or "",
        expected_statuses={
            AgentChangeStatus.PENDING_REVIEW,
            AgentChangeStatus.APPROVED,
            AgentChangeStatus.APPLIED,
        },
    )
    if isinstance(proposal, ToolExecutionResult):
        return proposal
    return group_preview_from_proposal(proposal), None


def _entry_ref_signature(entry_ref: EntryReferencePayload) -> tuple[str, str]:
    if entry_ref.entry_id is not None:
        return ("entry", entry_ref.entry_id)
    assert entry_ref.create_entry_proposal_id is not None
    return ("proposal", entry_ref.create_entry_proposal_id)


def _group_member_target_signature(target: GroupMemberTargetPayload) -> tuple[str, tuple[str, str]]:
    if isinstance(target, EntryGroupMemberTargetPayload):
        return ("entry", _entry_ref_signature(target.entry_ref))
    return ("child_group", group_ref_signature(target.group_ref))


def _group_member_signature(payload: dict[str, Any]) -> tuple[tuple[str, str], str, tuple[str, str]]:
    normalized_payload = normalize_group_member_payload(payload)
    group_ref = GroupReferencePayload.model_validate(normalized_payload.get("group_ref"))
    target = parse_group_member_target_payload(normalized_payload.get("target"))
    target_kind, target_signature = _group_member_target_signature(target)
    return (group_ref_signature(group_ref), target_kind, target_signature)


def _payload_group_member_target_type(payload: dict[str, Any]) -> str | None:
    normalized_payload = normalize_group_member_payload(payload)
    target = normalized_payload.get("target")
    if not isinstance(target, dict):
        return None
    target_type = target.get("target_type")
    return target_type if isinstance(target_type, str) else None


def pending_group_membership_conflict(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    target_signature = _group_member_signature(payload)
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type not in {AgentChangeType.CREATE_GROUP_MEMBER, AgentChangeType.DELETE_GROUP_MEMBER}:
            continue
        if _group_member_signature(item.payload_json) != target_signature:
            continue
        if item.change_type == change_type:
            return error_result(
                "a matching pending group membership proposal already exists in this thread",
                details={
                    "proposal_id": item.id,
                    "proposal_short_id": proposal_short_id(item.id),
                    "change_type": item.change_type.value,
                },
            )
        return error_result(
            "a conflicting pending group membership proposal already exists; update or remove it first",
            details={
                "proposal_id": item.id,
                "proposal_short_id": proposal_short_id(item.id),
                "change_type": item.change_type.value,
            },
        )
    return None


def _pending_parent_roles_for_group(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
) -> list[GroupMemberRole]:
    roles: list[GroupMemberRole] = []
    signature = group_ref_signature(group_ref)
    for item in pending_proposals_for_thread(context):
        if item.change_type != AgentChangeType.CREATE_GROUP_MEMBER:
            continue
        payload = item.payload_json
        item_group_ref = payload.get("group_ref")
        if not isinstance(item_group_ref, dict):
            continue
        if group_ref_signature(GroupReferencePayload.model_validate(item_group_ref)) != signature:
            continue
        raw_role = payload.get("member_role")
        if isinstance(raw_role, str):
            roles.append(GroupMemberRole(raw_role))
    return roles


def _existing_descendant_kinds(group: EntryGroup | None) -> set[EntryKind]:
    if group is None:
        return set()
    return {entry.kind for entry in descendant_entries_for_group(group)}


def _validate_group_member_add_rules(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    target: GroupMemberTargetPayload,
    member_role: GroupMemberRole | None,
) -> tuple[dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    group_resolution = resolved_group_type_from_ref(context, group_ref)
    if isinstance(group_resolution, ToolExecutionResult):
        return group_resolution
    parent_group_type, group_preview, existing_group, group_proposal = group_resolution
    canonical_parent_ref = GroupReferencePayload.model_validate(
        {"group_id": existing_group.id} if existing_group is not None else {"create_group_proposal_id": group_proposal.id}
    )
    member_resolution = _resolved_group_member_target_preview(context, target=target)
    if isinstance(member_resolution, ToolExecutionResult):
        return member_resolution
    member_preview, target_kind = member_resolution

    if isinstance(target, ChildGroupMemberTargetPayload):
        canonical_child_ref_resolution = canonical_group_ref_payload(
            context,
            group_ref=target.group_ref,
            expected_statuses={
                AgentChangeStatus.PENDING_REVIEW,
                AgentChangeStatus.APPROVED,
                AgentChangeStatus.APPLIED,
            },
        )
        if isinstance(canonical_child_ref_resolution, ToolExecutionResult):
            return canonical_child_ref_resolution
        canonical_child_ref = GroupReferencePayload.model_validate(canonical_child_ref_resolution[0])
        if group_ref_signature(canonical_parent_ref) == group_ref_signature(canonical_child_ref):
            return error_result("a group cannot contain itself")

    if parent_group_type == GroupType.SPLIT:
        if member_role is None:
            return error_result("split-group adds require member_role")
        existing_parent_count = (
            sum(
                1
                for membership in sorted_group_memberships(existing_group)
                if membership.member_role == GroupMemberRole.PARENT
            )
            if existing_group is not None
            else 0
        )
        pending_parent_count = _pending_parent_roles_for_group(
            context,
            group_ref=canonical_parent_ref,
        ).count(GroupMemberRole.PARENT)
        if member_role == GroupMemberRole.PARENT and existing_parent_count + pending_parent_count > 0:
            return error_result("split groups can have at most one parent member")
        if target_kind is not None:
            expected_kind = EntryKind.EXPENSE if member_role == GroupMemberRole.PARENT else EntryKind.INCOME
            if target_kind != expected_kind:
                return error_result(
                    "split group descendants must be EXPENSE for parent members and INCOME for child members",
                    details={"expected_kind": expected_kind.value, "actual_kind": target_kind.value},
                )
    elif member_role is not None:
        return error_result("member_role is only valid when the parent group type is SPLIT")

    if (
        existing_group is not None
        and isinstance(target, ChildGroupMemberTargetPayload)
        and existing_group.parent_membership is not None
    ):
        return error_result("nested groups cannot contain child groups")

    if parent_group_type == GroupType.RECURRING and target_kind is not None:
        descendant_kinds = _existing_descendant_kinds(existing_group)
        pending_kinds = {
            EntryKind(str(item.payload_json["member_preview"]["kind"]))
            for item in pending_proposals_for_thread(context)
            if item.change_type == AgentChangeType.CREATE_GROUP_MEMBER
            and isinstance(item.payload_json.get("group_ref"), dict)
            and group_ref_signature(GroupReferencePayload.model_validate(item.payload_json["group_ref"]))
            == group_ref_signature(canonical_parent_ref)
            and _payload_group_member_target_type(item.payload_json) == "entry"
            and isinstance(item.payload_json.get("member_preview"), dict)
            and isinstance(item.payload_json["member_preview"].get("kind"), str)
        }
        all_kinds = descendant_kinds | pending_kinds | {target_kind}
        if len(all_kinds) > 1:
            return error_result("recurring groups require all descendant entries to share the same kind")

    return group_preview, member_preview


def _validate_group_member_remove_rules(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    target: GroupMemberTargetPayload,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    group = match_existing_group_or_error(context, group_id=group_ref.group_id or "")
    if isinstance(group, ToolExecutionResult):
        return group

    member_resolution = _resolved_group_member_target_preview(
        context,
        target=target,
        enforce_add_membership_rules=False,
    )
    if isinstance(member_resolution, ToolExecutionResult):
        return member_resolution
    member_preview, _target_kind = member_resolution

    canonical_group_ref: dict[str, Any] = {"group_id": group.id}
    canonical_target: dict[str, Any]
    target_entry_id: str | None = None
    target_child_group_id: str | None = None

    if isinstance(target, EntryGroupMemberTargetPayload):
        entry = match_existing_entry_or_error(context, entry_id=target.entry_ref.entry_id or "")
        if isinstance(entry, ToolExecutionResult):
            return entry
        canonical_target = {"target_type": "entry", "entry_ref": {"entry_id": entry.id}}
        target_entry_id = entry.id
    else:
        child_group = match_existing_group_or_error(context, group_id=target.group_ref.group_id or "")
        if isinstance(child_group, ToolExecutionResult):
            return child_group
        canonical_target = {"target_type": "child_group", "group_ref": {"group_id": child_group.id}}
        target_child_group_id = child_group.id

    membership_exists = any(
        (membership.entry_id is not None and target_entry_id is not None and membership.entry_id == target_entry_id)
        or (
            membership.child_group_id is not None
            and target_child_group_id is not None
            and membership.child_group_id == target_child_group_id
        )
        for membership in sorted_group_memberships(group)
    )
    if not membership_exists:
        return error_result(
            "group does not currently contain that direct member",
            details={"group_id": group.id, "member": member_preview},
        )

    return canonical_group_ref, canonical_target, group_preview_from_existing(group), member_preview


def build_add_group_membership_payload(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    target: GroupMemberTargetPayload,
    member_role: GroupMemberRole | None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    if isinstance(target, ChildGroupMemberTargetPayload) and group_ref_signature(group_ref) == group_ref_signature(
        target.group_ref
    ):
        return error_result("a group cannot contain itself")

    previews = _validate_group_member_add_rules(
        context,
        group_ref=group_ref,
        target=target,
        member_role=member_role,
    )
    if isinstance(previews, ToolExecutionResult):
        return previews
    group_preview, member_preview = previews

    canonical_group_ref = canonical_group_ref_payload(
        context,
        group_ref=group_ref,
        expected_statuses={
            AgentChangeStatus.PENDING_REVIEW,
            AgentChangeStatus.APPROVED,
            AgentChangeStatus.APPLIED,
        },
    )
    if isinstance(canonical_group_ref, ToolExecutionResult):
        return canonical_group_ref

    canonical_target = _canonical_group_member_target_payload(
        context,
        target=target,
        expected_statuses={
            AgentChangeStatus.PENDING_REVIEW,
            AgentChangeStatus.APPROVED,
            AgentChangeStatus.APPLIED,
        },
    )
    if isinstance(canonical_target, ToolExecutionResult):
        return canonical_target

    payload = {
        "action": "add",
        "group_ref": canonical_group_ref[0],
        "target": canonical_target[0],
        "member_role": member_role.value if member_role is not None else None,
        "group_preview": group_preview,
        "member_preview": member_preview,
    }
    return payload, group_preview, member_preview


def build_remove_group_membership_payload(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    target: GroupMemberTargetPayload,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    removal = _validate_group_member_remove_rules(
        context,
        group_ref=group_ref,
        target=target,
    )
    if isinstance(removal, ToolExecutionResult):
        return removal
    canonical_group_ref, canonical_target, group_preview, member_preview = removal
    payload = {
        "action": "remove",
        "group_ref": canonical_group_ref,
        "target": canonical_target,
        "group_preview": group_preview,
        "member_preview": member_preview,
    }
    return payload, group_preview, member_preview


def propose_update_group_membership(
    context: ToolContext,
    args: ProposeUpdateGroupMembershipArgs,
) -> ToolExecutionResult:
    if args.action == "add":
        normalized = build_add_group_membership_payload(
            context,
            group_ref=args.group_ref,
            target=args.target,
            member_role=args.member_role,
        )
        if isinstance(normalized, ToolExecutionResult):
            return normalized
        payload, group_preview, member_preview = normalized
        conflict = pending_group_membership_conflict(
            context,
            change_type=AgentChangeType.CREATE_GROUP_MEMBER,
            payload=payload,
        )
        if conflict is not None:
            return conflict

        item = create_change_item(
            context,
            change_type=AgentChangeType.CREATE_GROUP_MEMBER,
            payload=payload,
            rationale_text="Agent proposed adding a direct group member.",
        )
        preview = {
            "action": "add",
            "group": group_preview,
            "member": member_preview,
            "member_role": payload["member_role"],
        }
        return proposal_result("proposed group membership add", preview=preview, item=item)

    normalized = build_remove_group_membership_payload(
        context,
        group_ref=args.group_ref,
        target=args.target,
    )
    if isinstance(normalized, ToolExecutionResult):
        return normalized
    payload, _group_preview, member_preview = normalized
    conflict = pending_group_membership_conflict(
        context,
        change_type=AgentChangeType.DELETE_GROUP_MEMBER,
        payload=payload,
    )
    if conflict is not None:
        return conflict

    item = create_change_item(
        context,
        change_type=AgentChangeType.DELETE_GROUP_MEMBER,
        payload=payload,
        rationale_text="Agent proposed removing a direct group member.",
    )
    preview = {
        "action": "remove",
        "group": payload["group_preview"],
        "member": member_preview,
    }
    return proposal_result("proposed group membership removal", preview=preview, item=item)
