# CALLING SPEC:
# - Purpose: provide the `contracts_settings` module.
# - Inputs: callers that import `backend/contracts_settings.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `contracts_settings`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.validation.runtime_settings import (
    normalize_agent_model_items_or_none,
    normalize_currency_code_or_none,
    normalize_text_or_none,
    normalize_user_memory_items_or_none,
    validate_agent_api_key_or_none,
    validate_agent_base_url_or_none,
    validate_user_memory_size,
)

RuntimeSettingsWriteField = Literal[
    "user_memory",
    "default_currency_code",
    "dashboard_currency_code",
    "agent_model",
    "entry_tagging_model",
    "available_agent_models",
    "agent_max_steps",
    "agent_bulk_max_concurrent_threads",
    "agent_retry_max_attempts",
    "agent_retry_initial_wait_seconds",
    "agent_retry_max_wait_seconds",
    "agent_retry_backoff_multiplier",
    "agent_max_image_size_bytes",
    "agent_max_images_per_message",
    "agent_base_url",
    "agent_api_key",
]


class RuntimeSettingsWriteFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_memory: list[str] | None = None
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    dashboard_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    agent_model: str | None = Field(default=None, max_length=255)
    entry_tagging_model: str | None = Field(default=None, max_length=255)
    available_agent_models: list[str] | None = None
    agent_max_steps: int | None = Field(default=None, ge=1, le=500)
    agent_bulk_max_concurrent_threads: int | None = Field(default=None, ge=1, le=16)
    agent_retry_max_attempts: int | None = Field(default=None, ge=1, le=10)
    agent_retry_initial_wait_seconds: float | None = Field(default=None, ge=0.0, le=30.0)
    agent_retry_max_wait_seconds: float | None = Field(default=None, ge=0.0, le=120.0)
    agent_retry_backoff_multiplier: float | None = Field(default=None, ge=1.0, le=10.0)
    agent_max_image_size_bytes: int | None = Field(default=None, ge=1024, le=104857600)
    agent_max_images_per_message: int | None = Field(default=None, ge=1, le=12)
    agent_base_url: str | None = Field(default=None, max_length=500)
    agent_api_key: str | None = Field(default=None, max_length=500)

    @field_validator("agent_model", "entry_tagging_model", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_text_or_none(str(value))

    @field_validator("user_memory", mode="before")
    @classmethod
    def normalize_optional_user_memory(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str) or not isinstance(value, list):
            raise ValueError("user_memory must be a list of strings")
        return validate_user_memory_size(
            normalize_user_memory_items_or_none(str(item) for item in value)
        )

    @field_validator("available_agent_models", mode="before")
    @classmethod
    def normalize_optional_available_agent_models(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str) or not isinstance(value, list):
            raise ValueError("available_agent_models must be a list of strings")
        return normalize_agent_model_items_or_none(str(item) for item in value)

    @field_validator("default_currency_code", "dashboard_currency_code", mode="before")
    @classmethod
    def normalize_optional_currency(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_currency_code_or_none(str(value))

    @field_validator("agent_base_url", mode="before")
    @classmethod
    def validate_agent_base_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        return validate_agent_base_url_or_none(str(value))

    @field_validator("agent_api_key", mode="before")
    @classmethod
    def validate_agent_api_key(cls, value: Any) -> str | None:
        if value is None:
            return None
        return validate_agent_api_key_or_none(str(value))

    def includes(self, field: RuntimeSettingsWriteField) -> bool:
        return field in self.model_fields_set
