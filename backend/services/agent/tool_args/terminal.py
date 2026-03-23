# CALLING SPEC:
# - Purpose: define argument contracts for the terminal tool.
# - Inputs: callers that import `terminal.py` and pass CLI-style terminal fields.
# - Outputs: validated Pydantic models for terminal execution.
# - Side effects: module-local validation only.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.agent.payload_normalization import normalize_loose_text


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunTerminalArgs(ToolArgsModel):
    command: str = Field(
        min_length=1,
        description=(
            "Shell command to execute verbatim via `bash -lc`. "
            "May include newlines, pipes, redirects, command substitution, or heredocs."
        ),
    )
    cwd: str | None = Field(
        default=None,
        description="Optional working directory inside the workspace container. Defaults to the writable scratch root `/workspace/scratch`.",
    )
    timeout_seconds: int = Field(
        default=120,
        ge=1,
        le=600,
        description="Command timeout in seconds. Defaults to 120. Allowed range: 1 to 600.",
    )

    @field_validator("command")
    @classmethod
    def normalize_command(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value cannot be empty")
        return value

    @field_validator("cwd")
    @classmethod
    def normalize_cwd(cls, value: str | None) -> str | None:
        return normalize_loose_text(value)
