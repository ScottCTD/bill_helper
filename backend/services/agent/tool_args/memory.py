# CALLING SPEC:
# - Purpose: implement focused service logic for `memory`.
# - Inputs: callers that import `backend/services/agent/tool_args/memory.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `memory`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.validation.runtime_settings import (
    normalize_user_memory_items_or_none,
    validate_user_memory_size,
)


class AddUserMemoryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_items: list[str] = Field(
        min_length=1,
        max_length=20,
        description=(
            "New persistent memory items to append. Each item should be a short standalone "
            "user preference, rule, or hint."
        ),
    )

    @field_validator("memory_items")
    @classmethod
    def normalize_memory_items(cls, value: list[str]) -> list[str]:
        normalized = validate_user_memory_size(normalize_user_memory_items_or_none(value))
        if normalized is None:
            raise ValueError("memory_items must include at least one non-empty item")
        return normalized
