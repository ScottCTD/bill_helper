from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.config import SHARED_DATA_DIR, _env_files, ensure_env_file_variables_loaded


def _default_data_dir() -> Path:
    return SHARED_DATA_DIR / "telegram"


def _normalize_text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


class TelegramSettings(BaseSettings):
    bot_token: str = Field(
        validation_alias=AliasChoices("TELEGRAM_BOT_TOKEN", "BILL_HELPER_TELEGRAM_BOT_TOKEN")
    )
    webhook_secret: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TELEGRAM_WEBHOOK_SECRET",
            "BILL_HELPER_TELEGRAM_WEBHOOK_SECRET",
        ),
    )
    telegram_api_base_url: str = Field(
        default="https://api.telegram.org",
        validation_alias=AliasChoices(
            "TELEGRAM_API_BASE_URL",
            "BILL_HELPER_TELEGRAM_API_BASE_URL",
        ),
    )
    backend_base_url: str = Field(
        default="http://localhost:8000/api/v1",
        validation_alias=AliasChoices(
            "TELEGRAM_BACKEND_BASE_URL",
            "BILL_HELPER_TELEGRAM_BACKEND_BASE_URL",
        ),
    )
    backend_auth_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "TELEGRAM_BACKEND_AUTH_TOKEN",
            "BILL_HELPER_TELEGRAM_BACKEND_AUTH_TOKEN",
        ),
    )
    backend_auth_headers: dict[str, str] = Field(
        default_factory=dict,
        validation_alias=AliasChoices(
            "TELEGRAM_BACKEND_AUTH_HEADERS",
            "BILL_HELPER_TELEGRAM_BACKEND_AUTH_HEADERS",
        ),
    )
    data_dir: Path = Field(
        default_factory=_default_data_dir,
        validation_alias=AliasChoices("TELEGRAM_DATA_DIR", "BILL_HELPER_TELEGRAM_DATA_DIR"),
    )
    state_path: Path | None = Field(
        default=None,
        validation_alias=AliasChoices("TELEGRAM_STATE_PATH", "BILL_HELPER_TELEGRAM_STATE_PATH"),
    )

    @field_validator("bot_token", mode="before")
    @classmethod
    def normalize_required_text(cls, value: Any) -> str:
        normalized = _normalize_text_or_none(value)
        if normalized is None:
            raise ValueError("value must not be empty")
        return normalized

    @field_validator("webhook_secret", "backend_auth_token", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        return _normalize_text_or_none(value)

    @field_validator("telegram_api_base_url", "backend_base_url", mode="before")
    @classmethod
    def normalize_base_url(cls, value: Any) -> str:
        normalized = _normalize_text_or_none(value)
        if normalized is None:
            raise ValueError("base URL must not be empty")
        return normalized.rstrip("/")

    @field_validator("backend_auth_headers", mode="before")
    @classmethod
    def parse_backend_auth_headers(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return {}
            try:
                value = json.loads(normalized)
            except json.JSONDecodeError as exc:
                raise ValueError("backend auth headers must be valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("backend auth headers must be a JSON object")
        normalized_headers: dict[str, str] = {}
        for raw_key, raw_header_value in value.items():
            key = _normalize_text_or_none(raw_key)
            header_value = _normalize_text_or_none(raw_header_value)
            if key is None or header_value is None:
                raise ValueError("backend auth header keys and values must not be empty")
            normalized_headers[key] = header_value
        return normalized_headers

    @model_validator(mode="after")
    def derive_state_path(self) -> TelegramSettings:
        if self.state_path is None:
            self.state_path = self.data_dir / "chat_state.json"
        return self

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    def build_backend_headers(self) -> dict[str, str]:
        headers = dict(self.backend_auth_headers)
        if self.backend_auth_token and "Authorization" not in headers:
            headers["Authorization"] = f"Bearer {self.backend_auth_token}"
        return headers

    model_config = SettingsConfigDict(
        env_file=_env_files,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> TelegramSettings:
    ensure_env_file_variables_loaded()
    return TelegramSettings()