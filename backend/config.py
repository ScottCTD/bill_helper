from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bill Helper"
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./.data/bill_helper.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    current_user_name: str = "scott"
    default_currency_code: str = Field(
        default="CAD",
        validation_alias=AliasChoices("DEFAULT_CURRENCY_CODE", "BILL_HELPER_DEFAULT_CURRENCY_CODE"),
    )
    dashboard_currency_code: str = Field(
        default="CAD",
        validation_alias=AliasChoices("DASHBOARD_CURRENCY_CODE", "BILL_HELPER_DASHBOARD_CURRENCY_CODE"),
    )
    openrouter_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "BILL_HELPER_OPENROUTER_API_KEY"),
    )
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    agent_model: str = "google/gemini-3-flash-preview"
    agent_max_steps: int = 100
    agent_retry_max_attempts: int = Field(default=3, ge=1, le=10)
    agent_retry_initial_wait_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    agent_retry_max_wait_seconds: float = Field(default=4.0, ge=0.0, le=120.0)
    agent_retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    agent_max_image_size_bytes: int = 5 * 1024 * 1024
    agent_max_images_per_message: int = 4

    model_config = SettingsConfigDict(
        env_prefix="BILL_HELPER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
