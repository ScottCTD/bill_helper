from __future__ import annotations

from unittest.mock import patch

from backend.config import get_settings
from backend.database import get_session_maker
from backend.models_settings import RuntimeSettings
from backend.services.runtime_settings import (
    append_user_memory_items,
    build_runtime_settings_view,
    resolve_runtime_settings,
    update_runtime_settings_override,
)
from backend.services.runtime_settings_contracts import RuntimeSettingsPatch


def test_resolve_runtime_settings_applies_override_and_sanitization() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        # Intentionally bypass API validators to cover service-time sanitization paths.
        db.add(
            RuntimeSettings(
                scope="default",
                default_currency_code="cad",
                dashboard_currency_code="usd",
                agent_max_steps=0,
                agent_bulk_max_concurrent_threads=99,
                agent_retry_max_attempts=0,
                agent_max_images_per_message=0,
                agent_max_image_size_bytes=10,
            )
        )
        db.commit()

        resolved = resolve_runtime_settings(db)
        assert resolved.default_currency_code == "CAD"
        assert resolved.dashboard_currency_code == "USD"
        assert resolved.agent_max_steps >= 1
        assert resolved.agent_bulk_max_concurrent_threads == get_settings().agent_bulk_max_concurrent_threads
        assert resolved.agent_retry_max_attempts >= 1
        assert resolved.agent_max_images_per_message >= 1
        assert resolved.agent_max_image_size_bytes >= 1024
    finally:
        db.close()


def test_build_runtime_settings_read_prefers_request_principal_name() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        update_runtime_settings_override(
            db,
            RuntimeSettingsPatch(agent_model="openai/gpt-4.1-mini"),
        )
        db.commit()

        payload = build_runtime_settings_view(db, principal_name="alice")
        assert payload.current_user_name == "alice"
        assert payload.agent_model == "openai/gpt-4.1-mini"
        assert payload.available_agent_models == [
            get_settings().agent_model,
            "openai/gpt-4.1-mini",
            "openrouter/qwen/qwen3.5-27b",
        ]
        assert payload.overrides.agent_model == "openai/gpt-4.1-mini"
        assert payload.agent_bulk_max_concurrent_threads == get_settings().agent_bulk_max_concurrent_threads
    finally:
        db.close()


def test_resolve_runtime_settings_does_not_treat_openrouter_env_as_custom_override(
    monkeypatch,
) -> None:
    monkeypatch.delenv("AGENT_API_KEY", raising=False)
    monkeypatch.delenv("BILL_HELPER_AGENT_API_KEY", raising=False)
    monkeypatch.delenv("AGENT_BASE_URL", raising=False)
    monkeypatch.delenv("BILL_HELPER_AGENT_BASE_URL", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    get_settings.cache_clear()

    make_session = get_session_maker()
    db = make_session()
    try:
        resolved = resolve_runtime_settings(db)
        assert resolved.agent_api_key is None
        assert resolved.agent_base_url is None
    finally:
        db.close()
        get_settings.cache_clear()


def test_build_runtime_settings_read_reports_provider_credentials_without_custom_override() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        with patch(
            "backend.services.runtime_settings.validate_litellm_environment",
            return_value=(True, [], get_settings().agent_model),
        ):
            payload = build_runtime_settings_view(db)
        assert payload.agent_api_key_configured is True
        assert payload.overrides.agent_api_key_configured is False
    finally:
        db.close()


def test_resolve_runtime_settings_uses_override_available_agent_models_and_keeps_default_model_present() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        update_runtime_settings_override(
            db,
            RuntimeSettingsPatch(
                agent_model="openai/gpt-4.1-mini",
                available_agent_models=["bedrock/us.anthropic.claude-sonnet-4-6"],
            ),
        )
        db.commit()

        resolved = resolve_runtime_settings(db)
        payload = build_runtime_settings_view(db)

        assert resolved.available_agent_models == [
            "bedrock/us.anthropic.claude-sonnet-4-6",
            "openai/gpt-4.1-mini",
        ]
        assert payload.available_agent_models == resolved.available_agent_models
        assert payload.overrides.available_agent_models == [
            "bedrock/us.anthropic.claude-sonnet-4-6"
        ]
    finally:
        db.close()


def test_resolve_runtime_settings_parses_legacy_multiline_user_memory() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        db.add(
            RuntimeSettings(
                scope="default",
                user_memory="Prefers terse answers.\n- Works in CAD.",
            )
        )
        db.commit()

        resolved = resolve_runtime_settings(db)
        assert resolved.user_memory == ["Prefers terse answers.", "Works in CAD."]
    finally:
        db.close()


def test_append_user_memory_items_deduplicates_and_persists_items() -> None:
    make_session = get_session_maker()
    db = make_session()
    try:
        update_runtime_settings_override(
            db,
            RuntimeSettingsPatch(user_memory=["Prefers terse answers."]),
        )
        db.commit()

        added_items, all_items = append_user_memory_items(
            db,
            items=["prefers terse answers.", "Works in CAD."],
        )
        db.commit()

        assert added_items == ["Works in CAD."]
        assert all_items == ["Prefers terse answers.", "Works in CAD."]
        assert build_runtime_settings_view(db).user_memory == all_items
    finally:
        db.close()
