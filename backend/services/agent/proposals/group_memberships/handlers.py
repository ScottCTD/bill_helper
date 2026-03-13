# CALLING SPEC:
# - Purpose: implement focused service logic for `handlers`.
# - Inputs: callers that import `backend/services/agent/proposals/group_memberships/handlers.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `handlers`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.enums_finance import GroupMemberRole
from backend.services.agent.change_contracts.groups import (
    ChildGroupMemberTargetPayload,
    GroupMemberTargetPayload,
    GroupReferencePayload,
)
from backend.services.agent.proposals.common import (
    create_change_item,
    pending_proposals_for_thread,
    proposal_result,
    proposal_short_id,
)
from backend.services.agent.proposals.group_memberships.common import (
    canonical_group_member_target_payload,
    group_member_signature,
)
from backend.services.agent.proposals.groups import canonical_group_ref_payload, group_ref_signature
from backend.services.agent.proposals.group_memberships.validation import (
    validate_group_member_add_rules,
    validate_group_member_remove_rules,
)
from backend.services.agent.tool_args.proposal_admin import ProposeUpdateGroupMembershipArgs
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult


def pending_group_membership_conflict(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    target_signature = group_member_signature(payload)
    for item in pending_proposals_for_thread(context):
        if exclude_item_id is not None and item.id == exclude_item_id:
            continue
        if item.change_type not in {AgentChangeType.CREATE_GROUP_MEMBER, AgentChangeType.DELETE_GROUP_MEMBER}:
            continue
        if group_member_signature(item.payload_json) != target_signature:
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

    previews = validate_group_member_add_rules(
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

    canonical_target = canonical_group_member_target_payload(
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
    removal = validate_group_member_remove_rules(
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
