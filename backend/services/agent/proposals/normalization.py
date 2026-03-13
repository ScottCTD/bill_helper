# CALLING SPEC:
# - Purpose: implement focused service logic for `normalization`.
# - Inputs: callers that import `backend/services/agent/proposals/normalization.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `normalization`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from backend.enums_agent import AgentChangeType
from backend.services.agent.proposals.normalization_catalog import CATALOG_PAYLOAD_NORMALIZERS
from backend.services.agent.proposals.normalization_entries import ENTRY_PAYLOAD_NORMALIZERS
from backend.services.agent.proposals.normalization_groups import GROUP_PAYLOAD_NORMALIZERS
from backend.services.agent.tool_types import ToolContext


ProposalPayloadNormalizer = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]

PAYLOAD_NORMALIZERS: dict[AgentChangeType, ProposalPayloadNormalizer] = {
    **CATALOG_PAYLOAD_NORMALIZERS,
    **ENTRY_PAYLOAD_NORMALIZERS,
    **GROUP_PAYLOAD_NORMALIZERS,
}


def normalize_payload_for_change_type(
    context: ToolContext,
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
) -> dict[str, Any]:
    normalizer = PAYLOAD_NORMALIZERS.get(change_type)
    if normalizer is None:
        raise ValueError(f"unsupported proposal change type: {change_type.value}")
    return normalizer(context, payload)
