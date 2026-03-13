# CALLING SPEC:
# - Purpose: implement focused service logic for `normalization_groups`.
# - Inputs: callers that import `backend/services/agent/proposals/normalization_groups.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `normalization_groups`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts.groups import (
    CreateGroupMemberPayload,
    CreateGroupPayload,
    DeleteGroupMemberPayload,
    DeleteGroupPayload,
    UpdateGroupPayload,
)
from backend.services.agent.group_references import group_detail_public_record
from backend.services.agent.proposals.group_memberships import (
    build_add_group_membership_payload,
    build_remove_group_membership_payload,
)
from backend.services.agent.proposals.groups import (
    group_preview_from_existing,
    match_existing_group_or_error,
)
from backend.services.agent.proposals.normalization_common import (
    parse_typed_change_payload,
    raise_normalization_error,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult


def normalize_create_group_payload(_context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_GROUP,
        payload=payload,
        model_type=CreateGroupPayload,
    )
    return parsed.model_dump(mode="json")


def normalize_update_group_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.UPDATE_GROUP,
        payload={"group_id": payload.get("group_id"), "patch": payload.get("patch")},
        model_type=UpdateGroupPayload,
    )
    group = match_existing_group_or_error(context, group_id=parsed.group_id)
    if isinstance(group, ToolExecutionResult):
        raise_normalization_error(group, default_message="group not found")
    return {
        "group_id": group.id,
        "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        "current": group_preview_from_existing(group),
        "target": group_detail_public_record(group),
    }


def normalize_delete_group_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_GROUP,
        payload={"group_id": payload.get("group_id")},
        model_type=DeleteGroupPayload,
    )
    group = match_existing_group_or_error(context, group_id=parsed.group_id)
    if isinstance(group, ToolExecutionResult):
        raise_normalization_error(group, default_message="group not found")
    return {
        "group_id": group.id,
        "target": group_detail_public_record(group),
    }


def normalize_create_group_member_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_GROUP_MEMBER,
        payload=payload,
        model_type=CreateGroupMemberPayload,
    )
    normalized = build_add_group_membership_payload(
        context,
        group_ref=parsed.group_ref,
        target=parsed.target,
        member_role=parsed.member_role,
    )
    if isinstance(normalized, ToolExecutionResult):
        raise_normalization_error(normalized, default_message="invalid group membership")
    normalized_payload, _group_preview, _member_preview = normalized
    return normalized_payload


def normalize_delete_group_member_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_GROUP_MEMBER,
        payload=payload,
        model_type=DeleteGroupMemberPayload,
    )
    normalized = build_remove_group_membership_payload(
        context,
        group_ref=parsed.group_ref,
        target=parsed.target,
    )
    if isinstance(normalized, ToolExecutionResult):
        raise_normalization_error(normalized, default_message="invalid group membership")
    normalized_payload, _group_preview, _member_preview = normalized
    return normalized_payload


GROUP_PAYLOAD_NORMALIZERS = {
    AgentChangeType.CREATE_GROUP: normalize_create_group_payload,
    AgentChangeType.UPDATE_GROUP: normalize_update_group_payload,
    AgentChangeType.DELETE_GROUP: normalize_delete_group_payload,
    AgentChangeType.CREATE_GROUP_MEMBER: normalize_create_group_member_payload,
    AgentChangeType.DELETE_GROUP_MEMBER: normalize_delete_group_member_payload,
}
