from __future__ import annotations

from backend.database import get_session_maker
from backend.models_finance import RuntimeSettings
from backend.services.runtime_settings import (
    build_runtime_settings_read,
    resolve_runtime_settings,
    update_runtime_settings_override,
)
from backend.schemas_finance import RuntimeSettingsUpdate


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
            RuntimeSettingsUpdate(agent_model="openai/gpt-4.1-mini"),
        )
        db.commit()

        payload = build_runtime_settings_read(db, principal_name="alice")
        assert payload.current_user_name == "alice"
        assert payload.agent_model == "openai/gpt-4.1-mini"
        assert payload.overrides.agent_model == "openai/gpt-4.1-mini"
    finally:
        db.close()
