# CALLING SPEC:
# - Purpose: define argument contracts for the workspace terminal tool.
# - Inputs: callers that import `workspace_command.py` and pass CLI-style terminal fields.
# - Outputs: validated Pydantic models for workspace command execution.
# - Side effects: module-local validation only.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.services.agent.payload_normalization import normalize_loose_text, normalize_required_text


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunWorkspaceCommandArgs(ToolArgsModel):
    command: str = Field(
        min_length=1,
        description=(
            "Shell command to run inside the current user's workspace container. "
            "Use `bh` for Bill Helper app operations and standard shell commands for local file work."
        ),
    )
    cwd: str | None = Field(
        default=None,
        description="Optional working directory inside the workspace container. Defaults to /workspace/workspace.",
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
        return normalize_required_text(value)

    @field_validator("cwd")
    @classmethod
    def normalize_cwd(cls, value: str | None) -> str | None:
        return normalize_loose_text(value)
