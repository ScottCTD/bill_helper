from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.contracts_settings import RuntimeSettingsWriteFields


class RuntimeSettingsOverridesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_memory: list[str] | None = None
    default_currency_code: str | None = None
    dashboard_currency_code: str | None = None
    agent_model: str | None = None
    entry_tagging_model: str | None = None
    available_agent_models: list[str] | None = None
    agent_max_steps: int | None = None
    agent_bulk_max_concurrent_threads: int | None = None
    agent_retry_max_attempts: int | None = None
    agent_retry_initial_wait_seconds: float | None = None
    agent_retry_max_wait_seconds: float | None = None
    agent_retry_backoff_multiplier: float | None = None
    agent_max_image_size_bytes: int | None = None
    agent_max_images_per_message: int | None = None
    agent_base_url: str | None = None
    agent_api_key_configured: bool = False


class RuntimeSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_memory: list[str] | None = None
    default_currency_code: str
    dashboard_currency_code: str
    agent_model: str
    entry_tagging_model: str | None = None
    available_agent_models: list[str]
    agent_max_steps: int
    agent_bulk_max_concurrent_threads: int
    agent_retry_max_attempts: int
    agent_retry_initial_wait_seconds: float
    agent_retry_max_wait_seconds: float
    agent_retry_backoff_multiplier: float
    agent_max_image_size_bytes: int
    agent_max_images_per_message: int
    agent_base_url: str | None = None
    agent_api_key_configured: bool = False
    overrides: RuntimeSettingsOverridesRead


class RuntimeSettingsUpdate(RuntimeSettingsWriteFields):
    model_config = ConfigDict(extra="forbid")
