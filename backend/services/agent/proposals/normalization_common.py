# CALLING SPEC:
# - Purpose: implement focused service logic for `normalization_common`.
# - Inputs: callers that import `backend/services/agent/proposals/normalization_common.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `normalization_common`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts import parse_change_payload
from backend.services.agent.tool_types import ToolExecutionResult


TChangePayload = TypeVar("TChangePayload", bound=BaseModel)


def parse_typed_change_payload(
    *,
    change_type: AgentChangeType,
    payload: dict[str, Any],
    model_type: type[TChangePayload],
) -> TChangePayload:
    parsed = parse_change_payload(change_type, payload)
    if not isinstance(parsed, model_type):  # pragma: no cover - enum/model map guard
        raise ValueError(f"unexpected payload model for change type: {change_type.value}")
    return parsed


def raise_normalization_error(result: ToolExecutionResult, *, default_message: str) -> None:
    raise ValueError(str(result.output_json.get("summary", default_message)))
