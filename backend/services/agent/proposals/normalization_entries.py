# CALLING SPEC:
# - Purpose: implement focused service logic for `normalization_entries`.
# - Inputs: callers that import `backend/services/agent/proposals/normalization_entries.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `normalization_entries`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts.entries import (
    CreateEntryPayload,
    DeleteEntryPayload,
    UpdateEntryPayload,
)
from backend.services.agent.proposals.entries import (
    normalize_update_entry_patch_for_payload,
    normalized_entry_reference_payload,
    proposal_payload_from_create_entry_args,
    validate_create_entry_entity_references,
    validate_update_entry_entity_patch,
)
from backend.services.agent.proposals.normalization_common import parse_typed_change_payload
from backend.services.agent.tool_types import ToolContext


def normalize_create_entry_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.CREATE_ENTRY,
        payload=payload,
        model_type=CreateEntryPayload,
    )
    validate_create_entry_entity_references(
        context,
        from_entity=parsed.from_entity,
        to_entity=parsed.to_entity,
    )
    return proposal_payload_from_create_entry_args(context, parsed)


def normalize_update_entry_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.UPDATE_ENTRY,
        payload={
            "entry_id": payload.get("entry_id"),
            "selector": payload.get("selector"),
            "patch": payload.get("patch"),
        },
        model_type=UpdateEntryPayload,
    )
    validate_update_entry_entity_patch(context, parsed.patch)
    normalized_payload = normalized_entry_reference_payload(
        context,
        entry_id=parsed.entry_id,
        selector=parsed.selector,
    )
    normalized_payload["patch"] = normalize_update_entry_patch_for_payload(parsed.patch)
    return normalized_payload


def normalize_delete_entry_payload(context: ToolContext, payload: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_typed_change_payload(
        change_type=AgentChangeType.DELETE_ENTRY,
        payload={
            "entry_id": payload.get("entry_id"),
            "selector": payload.get("selector"),
        },
        model_type=DeleteEntryPayload,
    )
    return normalized_entry_reference_payload(
        context,
        entry_id=parsed.entry_id,
        selector=parsed.selector,
    )


ENTRY_PAYLOAD_NORMALIZERS = {
    AgentChangeType.CREATE_ENTRY: normalize_create_entry_payload,
    AgentChangeType.UPDATE_ENTRY: normalize_update_entry_payload,
    AgentChangeType.DELETE_ENTRY: normalize_delete_entry_payload,
}
