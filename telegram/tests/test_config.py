from __future__ import annotations

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from telegram.config import TelegramSettings


def test_settings_parse_backend_auth_and_derive_state_path(tmp_path, monkeypatch):
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BOT_TOKEN", " bot-token ")
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_ALLOWED_USER_IDS", "12345, 67890")
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BACKEND_BASE_URL", "http://localhost:8000/api/v1/")
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BACKEND_AUTH_TOKEN", " secret-token ")
    monkeypatch.setenv(
        "BILL_HELPER_TELEGRAM_BACKEND_AUTH_HEADERS",
        '{"X-Trace-Id": "telegram"}',
    )
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_DATA_DIR", str(tmp_path))

    settings = TelegramSettings(_env_file=None)

    assert settings.bot_token == "bot-token"
    assert settings.allowed_user_ids == frozenset({12345, 67890})
    assert settings.backend_base_url == "http://localhost:8000/api/v1"
    assert settings.state_path == tmp_path / "chat_state.json"
    assert settings.build_backend_headers() == {
        "X-Trace-Id": "telegram",
        "Authorization": "Bearer secret-token",
    }
    assert settings.ensure_data_dir() == tmp_path


def test_settings_reject_invalid_backend_auth_headers(monkeypatch):
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BACKEND_AUTH_HEADERS", "not-json")

    with pytest.raises(SettingsError, match="backend_auth_headers"):
        TelegramSettings(_env_file=None)


def test_settings_default_to_empty_allowed_user_ids(monkeypatch):
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BOT_TOKEN", "bot-token")

    settings = TelegramSettings(_env_file=None)

    assert settings.allowed_user_ids == frozenset()


def test_settings_reject_invalid_allowed_user_ids(monkeypatch):
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("BILL_HELPER_TELEGRAM_ALLOWED_USER_IDS", '[12345, "not-a-number"]')

    with pytest.raises(ValidationError, match="allowed user IDs must be positive integers"):
        TelegramSettings(_env_file=None)
