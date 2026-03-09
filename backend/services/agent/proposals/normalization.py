from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts import parse_change_payload as parse_change_payload_model
from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload as ProposeCreateAccountArgs,
    CreateEntityPayload as ProposeCreateEntityArgs,
    CreateTagPayload as ProposeCreateTagArgs,
    DeleteAccountPayload as ProposeDeleteAccountArgs,
    DeleteEntityPayload as ProposeDeleteEntityArgs,
    DeleteTagPayload as ProposeDeleteTagArgs,
    UpdateAccountPayload as ProposeUpdateAccountArgs,
    UpdateEntityPayload as ProposeUpdateEntityArgs,
    UpdateTagPayload as ProposeUpdateTagArgs,
)
from backend.services.agent.change_contracts.entries import (
    CreateEntryPayload as ProposeCreateEntryArgs,
    DeleteEntryPayload as ProposeDeleteEntryArgs,
    UpdateEntryPayload as ProposeUpdateEntryArgs,
)
from backend.services.agent.change_contracts.groups import (
    CreateGroupMemberPayload,
    CreateGroupPayload as ProposeCreateGroupArgs,
    DeleteGroupMemberPayload,
    DeleteGroupPayload as ProposeDeleteGroupArgs,
    UpdateGroupPayload as ProposeUpdateGroupArgs,
)
from backend.services.agent.group_references import group_detail_public_record
from backend.services.agent.proposals.entries import (
    normalize_update_entry_patch_for_payload,
    normalized_entry_reference_payload,
    proposal_payload_from_create_entry_args,
    validate_create_entry_entity_references,
    validate_update_entry_entity_patch,
)
from backend.services.agent.proposals.group_memberships import (
    build_add_group_membership_payload,
    build_remove_group_membership_payload,
)
from backend.services.agent.proposals.groups import (
    group_preview_from_existing,
    match_existing_group_or_error,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.entities import ACCOUNT_CATEGORY_DETAIL
from backend.validation.finance_names import normalize_entity_category


TChangePayload = TypeVar("TChangePayload", bound=BaseModel)


def _parse_typed_change_payload(
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    model_type: type[TChangePayload],
) -> TChangePayload:
    parsed = parse_change_payload_model(change_type, payload)
    if not isinstance(parsed, model_type):  # pragma: no cover - enum/model map guard
        raise ValueError(f"unexpected payload model for change type: {change_type.value}")
    return parsed


def _raise_normalization_error(result: ToolExecutionResult, *, default_message: str) -> None:
    raise ValueError(str(result.output_json.get("summary", default_message)))


def normalize_payload_for_change_type(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if change_type == AgentChangeType.CREATE_TAG:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateTagArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_TAG:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateTagArgs,
        )
        normalized_payload: dict[str, Any] = {
            "name": parsed.name,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        }
        if isinstance(payload.get("current"), dict):
            normalized_payload["current"] = payload["current"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_TAG:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeDeleteTagArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.CREATE_ENTITY:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateEntityArgs,
        )
        if normalize_entity_category(parsed.category) == "account":
            raise ValueError(ACCOUNT_CATEGORY_DETAIL)
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_ENTITY:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateEntityArgs,
        )
        if normalize_entity_category(parsed.patch.category) == "account":
            raise ValueError(ACCOUNT_CATEGORY_DETAIL)
        normalized_payload = {
            "name": parsed.name,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        }
        if isinstance(payload.get("current"), dict):
            normalized_payload["current"] = payload["current"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_ENTITY:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeDeleteEntityArgs,
        )
        normalized_payload = parsed.model_dump(mode="json")
        if isinstance(payload.get("impact_preview"), dict):
            normalized_payload["impact_preview"] = payload["impact_preview"]
        return normalized_payload
    if change_type == AgentChangeType.CREATE_ACCOUNT:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateAccountArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_ACCOUNT:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={"name": payload.get("name"), "patch": payload.get("patch")},
            model_type=ProposeUpdateAccountArgs,
        )
        normalized_payload = {
            "name": parsed.name,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
        }
        if isinstance(payload.get("current"), dict):
            normalized_payload["current"] = payload["current"]
        return normalized_payload
    if change_type == AgentChangeType.DELETE_ACCOUNT:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeDeleteAccountArgs,
        )
        normalized_payload = parsed.model_dump(mode="json")
        if isinstance(payload.get("impact_preview"), dict):
            normalized_payload["impact_preview"] = payload["impact_preview"]
        return normalized_payload
    if change_type == AgentChangeType.CREATE_ENTRY:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateEntryArgs,
        )
        validate_create_entry_entity_references(
            context,
            from_entity=parsed.from_entity,
            to_entity=parsed.to_entity,
        )
        return proposal_payload_from_create_entry_args(context, parsed)
    if change_type == AgentChangeType.UPDATE_ENTRY:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={
                "entry_id": payload.get("entry_id"),
                "selector": payload.get("selector"),
                "patch": payload.get("patch"),
            },
            model_type=ProposeUpdateEntryArgs,
        )
        validate_update_entry_entity_patch(context, parsed.patch)
        normalized_payload = normalized_entry_reference_payload(
            context,
            entry_id=parsed.entry_id,
            selector=parsed.selector,
        )
        normalized_payload["patch"] = normalize_update_entry_patch_for_payload(parsed.patch)
        return normalized_payload
    if change_type == AgentChangeType.DELETE_ENTRY:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={
                "entry_id": payload.get("entry_id"),
                "selector": payload.get("selector"),
            },
            model_type=ProposeDeleteEntryArgs,
        )
        return normalized_entry_reference_payload(
            context,
            entry_id=parsed.entry_id,
            selector=parsed.selector,
        )
    if change_type == AgentChangeType.CREATE_GROUP:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=ProposeCreateGroupArgs,
        )
        return parsed.model_dump(mode="json")
    if change_type == AgentChangeType.UPDATE_GROUP:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={"group_id": payload.get("group_id"), "patch": payload.get("patch")},
            model_type=ProposeUpdateGroupArgs,
        )
        group = match_existing_group_or_error(context, group_id=parsed.group_id)
        if isinstance(group, ToolExecutionResult):
            _raise_normalization_error(group, default_message="group not found")
        normalized_payload = {
            "group_id": group.id,
            "patch": parsed.patch.model_dump(mode="json", exclude_unset=True),
            "current": group_preview_from_existing(group),
            "target": group_detail_public_record(group),
        }
        return normalized_payload
    if change_type == AgentChangeType.DELETE_GROUP:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload={"group_id": payload.get("group_id")},
            model_type=ProposeDeleteGroupArgs,
        )
        group = match_existing_group_or_error(context, group_id=parsed.group_id)
        if isinstance(group, ToolExecutionResult):
            _raise_normalization_error(group, default_message="group not found")
        return {
            "group_id": group.id,
            "target": group_detail_public_record(group),
        }
    if change_type == AgentChangeType.CREATE_GROUP_MEMBER:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
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
            _raise_normalization_error(normalized, default_message="invalid group membership")
        normalized_payload, _group_preview, _member_preview = normalized
        return normalized_payload
    if change_type == AgentChangeType.DELETE_GROUP_MEMBER:
        parsed = _parse_typed_change_payload(
            change_type=change_type,
            payload=payload,
            model_type=DeleteGroupMemberPayload,
        )
        normalized = build_remove_group_membership_payload(
            context,
            group_ref=parsed.group_ref,
            target=parsed.target,
        )
        if isinstance(normalized, ToolExecutionResult):
            _raise_normalization_error(normalized, default_message="invalid group membership")
        normalized_payload, _group_preview, _member_preview = normalized
        return normalized_payload
    raise ValueError(f"unsupported proposal change type: {change_type.value}")
