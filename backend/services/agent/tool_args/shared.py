# CALLING SPEC:
# - Purpose: implement focused service logic for `shared`.
# - Inputs: callers that import `backend/services/agent/tool_args/shared.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `shared`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


INTERMEDIATE_UPDATE_TOOL_NAME = "send_intermediate_update"


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArgs(ToolArgsModel):
    pass


class SendIntermediateUpdateArgs(ToolArgsModel):
    message: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "A short, user-visible progress note. Use plain text or inline markdown "
            "(e.g. **bold**, `code`, *italic*) for emphasis when helpful."
        ),
    )

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized
