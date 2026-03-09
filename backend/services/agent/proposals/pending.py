from __future__ import annotations

from copy import deepcopy

from pydantic import ValidationError

from backend.enums_agent import AgentChangeStatus, AgentChangeType
from backend.services.agent.change_contracts.patches import validate_patch_map_paths
from backend.services.agent.proposal_patching import apply_patch_map_to_payload
from backend.services.agent.proposals.common import proposal_short_id, resolve_pending_proposal_by_id
from backend.services.agent.proposals.group_memberships import pending_group_membership_conflict
from backend.services.agent.proposals.groups import (
    pending_create_group_conflict,
    pending_group_change_conflict,
)
from backend.services.agent.proposals.normalization import normalize_payload_for_change_type
from backend.services.agent.tool_args import RemovePendingProposalArgs, UpdatePendingProposalArgs
from backend.services.agent.tool_results import error_result, format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus


def _pending_group_proposal_conflict(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, object],
    exclude_item_id: str | None = None,
) -> ToolExecutionResult | None:
    if change_type == AgentChangeType.CREATE_GROUP:
        return pending_create_group_conflict(
            context,
            name=str(payload.get("name") or ""),
            group_type=str(payload.get("group_type") or ""),
            exclude_item_id=exclude_item_id,
        )
    if change_type in {AgentChangeType.UPDATE_GROUP, AgentChangeType.DELETE_GROUP}:
        return pending_group_change_conflict(
            context,
            change_type=change_type,
            group_id=str(payload.get("group_id") or ""),
            exclude_item_id=exclude_item_id,
        )
    if change_type in {AgentChangeType.CREATE_GROUP_MEMBER, AgentChangeType.DELETE_GROUP_MEMBER}:
        return pending_group_membership_conflict(
            context,
            change_type=change_type,
            payload=dict(payload),
            exclude_item_id=exclude_item_id,
        )
    return None


def update_pending_proposal(context: ToolContext, args: UpdatePendingProposalArgs) -> ToolExecutionResult:
    try:
        item = resolve_pending_proposal_by_id(context, args.proposal_id)
    except ValueError as exc:
        return error_result("invalid proposal id", details=str(exc))
    if item is None:
        return error_result(
            "pending proposal not found",
            details={"proposal_id": args.proposal_id},
        )

    if item.status != AgentChangeStatus.PENDING_REVIEW:
        return error_result(
            "only pending proposals can be updated",
            details={
                "proposal_id": item.id,
                "status": item.status.value,
            },
        )

    try:
        validate_patch_map_paths(item.change_type, args.patch_map)
        patched_payload = apply_patch_map_to_payload(item.payload_json, args.patch_map)
        normalized_payload = normalize_payload_for_change_type(
            context,
            change_type=item.change_type,
            payload=patched_payload,
        )
    except ValidationError as exc:
        return error_result("invalid proposal patch", details=exc.errors())
    except ValueError as exc:
        return error_result("invalid proposal patch", details=str(exc))

    conflict = _pending_group_proposal_conflict(
        context,
        change_type=item.change_type,
        payload=normalized_payload,
        exclude_item_id=item.id,
    )
    if conflict is not None:
        return conflict

    item.payload_json = normalized_payload
    context.db.add(item)
    context.db.flush()

    output_json = {
        "status": "OK",
        "summary": "updated pending proposal",
        "proposal_id": item.id,
        "proposal_short_id": proposal_short_id(item.id),
        "change_type": item.change_type.value,
        "item_status": item.status.value,
        "patch_fields": sorted(args.patch_map),
        "preview": normalized_payload,
    }
    output_lines = [
        "OK",
        "summary: updated pending proposal",
        f"proposal_id: {item.id}",
        f"proposal_short_id: {proposal_short_id(item.id)}",
        f"change_type: {item.change_type.value}",
        f"status: {item.status.value}",
        f"patch_fields: {sorted(args.patch_map)}",
        f"preview: {normalized_payload}",
    ]
    return ToolExecutionResult(
        output_text=format_lines(output_lines),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )


def remove_pending_proposal(context: ToolContext, args: RemovePendingProposalArgs) -> ToolExecutionResult:
    try:
        item = resolve_pending_proposal_by_id(context, args.proposal_id)
    except ValueError as exc:
        return error_result("invalid proposal id", details=str(exc))
    if item is None:
        return error_result(
            "pending proposal not found",
            details={"proposal_id": args.proposal_id},
        )

    if item.status != AgentChangeStatus.PENDING_REVIEW:
        return error_result(
            "only pending proposals can be removed",
            details={
                "proposal_id": item.id,
                "status": item.status.value,
            },
        )

    removed_payload = deepcopy(item.payload_json)
    removed_change_type = item.change_type.value
    removed_item_id = item.id
    removed_short_id = proposal_short_id(item.id)

    context.db.delete(item)
    context.db.flush()

    output_json = {
        "status": "OK",
        "summary": "removed pending proposal",
        "proposal_id": removed_item_id,
        "proposal_short_id": removed_short_id,
        "change_type": removed_change_type,
        "removed": True,
        "removed_preview": removed_payload,
    }
    output_lines = [
        "OK",
        "summary: removed pending proposal",
        f"proposal_id: {removed_item_id}",
        f"proposal_short_id: {removed_short_id}",
        f"change_type: {removed_change_type}",
        "removed: true",
        f"removed_preview: {removed_payload}",
    ]
    return ToolExecutionResult(
        output_text=format_lines(output_lines),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )
