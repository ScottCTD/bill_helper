# CALLING SPEC:
# - Purpose: define argument contracts for the read_image tool.
# - Inputs: callers that import `read_image.py` and pass workspace image paths.
# - Outputs: validated Pydantic models for image-on-demand tool execution.
# - Side effects: module-local validation only.
from __future__ import annotations

from pydantic import Field, field_validator

from backend.services.agent.payload_normalization import normalize_loose_text
from backend.services.agent.tool_args.shared import ToolArgsModel


class ReadImageArgs(ToolArgsModel):
    paths: list[str] = Field(
        min_length=1,
        description=(
            "Absolute image paths inside the current user's workspace container. "
            "Use paths already shown in attachment workspace hints or discovered in `/workspace`."
        ),
    )

    @field_validator("paths")
    @classmethod
    def normalize_paths(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            path = normalize_loose_text(item)
            if not path:
                raise ValueError("paths cannot contain empty values")
            if path in seen:
                continue
            seen.add(path)
            normalized.append(path)
        if not normalized:
            raise ValueError("paths cannot be empty")
        return normalized
