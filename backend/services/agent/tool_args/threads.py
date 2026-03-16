# CALLING SPEC:
# - Purpose: implement focused service logic for `threads`.
# - Inputs: callers that import `backend/services/agent/tool_args/threads.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `threads`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.validation.agent_threads import THREAD_TITLE_MAX_LENGTH, validate_thread_title


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RenameThreadArgs(ToolArgsModel):
    title: str = Field(
        min_length=1,
        max_length=THREAD_TITLE_MAX_LENGTH,
        description="Short thread title/topic in 1-3 words.",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return validate_thread_title(value)
