from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Annotated, Any

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    allowed_user_ids: Annotated[frozenset[int], NoDecode] = Field(
        default_factory=frozenset,
        validation_alias=AliasChoices(
            "TELEGRAM_ALLOWED_USER_IDS",
            "BILL_HELPER_TELEGRAM_ALLOWED_USER_IDS",
        ),
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

    @field_validator("allowed_user_ids", mode="before")
    @classmethod
    def parse_allowed_user_ids(cls, value: Any) -> frozenset[int]:
        if value is None:
            return frozenset()
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                return frozenset()
            if normalized.startswith("["):
                try:
                    value = json.loads(normalized)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "allowed user IDs must be a JSON array or comma-separated integers"
                    ) from exc
            else:
                value = normalized.split(",")
        if not isinstance(value, list | tuple | set | frozenset):
            raise ValueError("allowed user IDs must be a JSON array or comma-separated integers")

        normalized_ids: set[int] = set()
        for raw_item in value:
            if isinstance(raw_item, bool):
                raise ValueError("allowed user IDs must be positive integers")
            normalized_item = _normalize_text_or_none(raw_item)
            if normalized_item is None:
                raise ValueError("allowed user IDs must not contain empty values")
            try:
                user_id = int(normalized_item)
            except ValueError as exc:
                raise ValueError("allowed user IDs must be positive integers") from exc
            if user_id <= 0:
                raise ValueError("allowed user IDs must be positive integers")
            normalized_ids.add(user_id)
        return frozenset(normalized_ids)

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