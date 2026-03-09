from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.services.runtime_settings_normalization import (
    normalize_user_memory_items_or_none,
    validate_user_memory_size,
)


class AddUserMemoryArgs(BaseModel):
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
