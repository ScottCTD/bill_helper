# CALLING SPEC:
# - Purpose: implement focused service logic for `validation`.
# - Inputs: callers that import `backend/services/agent/proposals/group_memberships/validation.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `validation`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
from backend.services.agent.change_contracts.groups import (
    ChildGroupMemberTargetPayload,
    EntryGroupMemberTargetPayload,
    GroupMemberTargetPayload,
    GroupReferencePayload,
)
from backend.services.agent.proposals.common import pending_proposals_for_thread
from backend.services.agent.proposals.group_memberships.common import (
    canonical_group_member_target_payload,
    existing_descendant_kinds,
    payload_group_member_target_type,
    pending_parent_roles_for_group,
    resolved_group_member_target_preview,
)
from backend.services.agent.proposals.groups import (
    canonical_group_ref_payload,
    group_preview_from_existing,
    group_ref_signature,
    match_existing_group_or_error,
    resolved_group_type_from_ref,
    sorted_group_memberships,
)
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult


def validate_group_member_add_rules(
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
    member_resolution = resolved_group_member_target_preview(context, target=target)
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
        pending_parent_count = pending_parent_roles_for_group(
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
        descendant_kinds = existing_descendant_kinds(existing_group)
        pending_kinds = {
            EntryKind(str(item.payload_json["member_preview"]["kind"]))
            for item in pending_proposals_for_thread(context)
            if item.change_type == AgentChangeType.CREATE_GROUP_MEMBER
            and isinstance(item.payload_json.get("group_ref"), dict)
            and group_ref_signature(GroupReferencePayload.model_validate(item.payload_json["group_ref"]))
            == group_ref_signature(canonical_parent_ref)
            and payload_group_member_target_type(item.payload_json) == "entry"
            and isinstance(item.payload_json.get("member_preview"), dict)
            and isinstance(item.payload_json["member_preview"].get("kind"), str)
        }
        all_kinds = descendant_kinds | pending_kinds | {target_kind}
        if len(all_kinds) > 1:
            return error_result("recurring groups require all descendant entries to share the same kind")

    return group_preview, member_preview


def validate_group_member_remove_rules(
    context: ToolContext,
    *,
    group_ref: GroupReferencePayload,
    target: GroupMemberTargetPayload,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]] | ToolExecutionResult:
    group = match_existing_group_or_error(context, group_id=group_ref.group_id or "")
    if isinstance(group, ToolExecutionResult):
        return group

    member_resolution = resolved_group_member_target_preview(
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
        entry = canonical_group_member_target_payload(
            context,
            target=target,
        )
        if isinstance(entry, ToolExecutionResult):
            return entry
        canonical_target = entry[0]
        target_entry_id = canonical_target["entry_ref"]["entry_id"]
    else:
        child_group = canonical_group_member_target_payload(
            context,
            target=target,
        )
        if isinstance(child_group, ToolExecutionResult):
            return child_group
        canonical_target = child_group[0]
        target_child_group_id = canonical_target["group_ref"]["group_id"]

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
