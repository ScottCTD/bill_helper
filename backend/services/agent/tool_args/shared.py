from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


INTERMEDIATE_UPDATE_TOOL_NAME = "send_intermediate_update"


class EmptyArgs(BaseModel):
    pass


class SendIntermediateUpdateArgs(BaseModel):
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
