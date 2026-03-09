from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from backend.services.agent.threads import THREAD_TITLE_MAX_LENGTH, validate_thread_title


class RenameThreadArgs(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=THREAD_TITLE_MAX_LENGTH,
        description="Short thread title/topic in 1-5 words.",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return validate_thread_title(value)
