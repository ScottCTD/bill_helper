from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models import RuntimeSettings as RuntimeSettingsRow
from backend.schemas import RuntimeSettingsOverridesRead, RuntimeSettingsRead

RUNTIME_SETTINGS_SCOPE = "default"


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def _normalize_optional_multiline_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()
    return normalized or None


def _normalize_optional_currency(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    code = normalized.upper()
    if len(code) != 3:
        return None
    return code


def _normalize_optional_secret(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _sanitize_int(value: int, *, minimum: int, fallback: int) -> int:
    if value < minimum:
        return max(fallback, minimum)
    return value


def _sanitize_float(value: float, *, minimum: float, fallback: float) -> float:
    if value < minimum:
        return max(fallback, minimum)
    return value


@dataclass(slots=True, frozen=True)
class ResolvedRuntimeSettings:
    api_prefix: str
    current_user_name: str
    user_memory: str | None
    default_currency_code: str
    dashboard_currency_code: str
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    agent_model: str
    agent_max_steps: int
    agent_retry_max_attempts: int
    agent_retry_initial_wait_seconds: float
    agent_retry_max_wait_seconds: float
    agent_retry_backoff_multiplier: float
    agent_max_image_size_bytes: int
    agent_max_images_per_message: int
    agent_base_url: str | None
    agent_api_key: str | None


def get_runtime_settings_override(db: Session) -> RuntimeSettingsRow | None:
    return db.scalar(
        select(RuntimeSettingsRow).where(
            RuntimeSettingsRow.scope == RUNTIME_SETTINGS_SCOPE
        )
    )


def _ensure_runtime_settings_override(db: Session) -> RuntimeSettingsRow:
    existing = get_runtime_settings_override(db)
    if existing is not None:
        return existing
    created = RuntimeSettingsRow(scope=RUNTIME_SETTINGS_SCOPE)
    db.add(created)
    db.flush()
    return created


def update_runtime_settings_override(
    db: Session, updates: dict[str, Any]
) -> RuntimeSettingsRow:
    row = _ensure_runtime_settings_override(db)
    for field_name, value in updates.items():
        setattr(row, field_name, value)
    db.add(row)
    db.flush()
    return row


def resolve_runtime_settings(db: Session) -> ResolvedRuntimeSettings:
    defaults = get_settings()
    override = get_runtime_settings_override(db)

    current_user_name = (
        (
            _normalize_optional_text(override.current_user_name)
            if override is not None
            else None
        )
        or _normalize_optional_text(defaults.current_user_name)
        or "admin"
    )
    user_memory = (
        _normalize_optional_multiline_text(override.user_memory)
        if override is not None
        else None
    )
    default_currency_code = (
        (
            _normalize_optional_currency(override.default_currency_code)
            if override is not None
            else None
        )
        or _normalize_optional_currency(defaults.default_currency_code)
        or "CAD"
    )
    dashboard_currency_code = (
        (
            _normalize_optional_currency(override.dashboard_currency_code)
            if override is not None
            else None
        )
        or _normalize_optional_currency(defaults.dashboard_currency_code)
        or "CAD"
    )
    langfuse_public_key = _normalize_optional_secret(defaults.langfuse_public_key)
    langfuse_secret_key = _normalize_optional_secret(defaults.langfuse_secret_key)
    langfuse_host = _normalize_optional_text(defaults.langfuse_host)
    agent_model = (
        (
            _normalize_optional_text(override.agent_model)
            if override is not None
            else None
        )
        or _normalize_optional_text(defaults.agent_model)
        or "openrouter/qwen/qwen3.5-27b"
    )

    agent_max_steps = _sanitize_int(
        override.agent_max_steps
        if override and override.agent_max_steps is not None
        else defaults.agent_max_steps,
        minimum=1,
        fallback=defaults.agent_max_steps,
    )
    agent_retry_max_attempts = _sanitize_int(
        override.agent_retry_max_attempts
        if override and override.agent_retry_max_attempts is not None
        else defaults.agent_retry_max_attempts,
        minimum=1,
        fallback=defaults.agent_retry_max_attempts,
    )
    agent_retry_initial_wait_seconds = _sanitize_float(
        override.agent_retry_initial_wait_seconds
        if override and override.agent_retry_initial_wait_seconds is not None
        else defaults.agent_retry_initial_wait_seconds,
        minimum=0.0,
        fallback=defaults.agent_retry_initial_wait_seconds,
    )
    agent_retry_max_wait_seconds = _sanitize_float(
        override.agent_retry_max_wait_seconds
        if override and override.agent_retry_max_wait_seconds is not None
        else defaults.agent_retry_max_wait_seconds,
        minimum=0.0,
        fallback=defaults.agent_retry_max_wait_seconds,
    )
    agent_retry_backoff_multiplier = _sanitize_float(
        override.agent_retry_backoff_multiplier
        if override and override.agent_retry_backoff_multiplier is not None
        else defaults.agent_retry_backoff_multiplier,
        minimum=1.0,
        fallback=defaults.agent_retry_backoff_multiplier,
    )
    agent_max_image_size_bytes = _sanitize_int(
        override.agent_max_image_size_bytes
        if override and override.agent_max_image_size_bytes is not None
        else defaults.agent_max_image_size_bytes,
        minimum=1024,
        fallback=defaults.agent_max_image_size_bytes,
    )
    agent_max_images_per_message = _sanitize_int(
        override.agent_max_images_per_message
        if override and override.agent_max_images_per_message is not None
        else defaults.agent_max_images_per_message,
        minimum=1,
        fallback=defaults.agent_max_images_per_message,
    )
    agent_base_url = (
        _normalize_optional_text(override.agent_base_url)
        if override and override.agent_base_url is not None
        else None
    ) or _normalize_optional_text(defaults.agent_base_url)
    agent_api_key = (
        _normalize_optional_secret(override.agent_api_key)
        if override and override.agent_api_key is not None
        else None
    ) or _normalize_optional_secret(defaults.agent_api_key)

    return ResolvedRuntimeSettings(
        api_prefix=defaults.api_prefix,
        current_user_name=current_user_name,
        user_memory=user_memory,
        default_currency_code=default_currency_code,
        dashboard_currency_code=dashboard_currency_code,
        langfuse_public_key=langfuse_public_key,
        langfuse_secret_key=langfuse_secret_key,
        langfuse_host=langfuse_host,
        agent_model=agent_model,
        agent_max_steps=agent_max_steps,
        agent_retry_max_attempts=agent_retry_max_attempts,
        agent_retry_initial_wait_seconds=agent_retry_initial_wait_seconds,
        agent_retry_max_wait_seconds=agent_retry_max_wait_seconds,
        agent_retry_backoff_multiplier=agent_retry_backoff_multiplier,
        agent_max_image_size_bytes=agent_max_image_size_bytes,
        agent_max_images_per_message=agent_max_images_per_message,
        agent_base_url=agent_base_url,
        agent_api_key=agent_api_key,
    )


def build_runtime_settings_read(db: Session) -> RuntimeSettingsRead:
    override = get_runtime_settings_override(db)
    resolved = resolve_runtime_settings(db)

    return RuntimeSettingsRead(
        current_user_name=resolved.current_user_name,
        user_memory=resolved.user_memory,
        default_currency_code=resolved.default_currency_code,
        dashboard_currency_code=resolved.dashboard_currency_code,
        agent_model=resolved.agent_model,
        agent_max_steps=resolved.agent_max_steps,
        agent_retry_max_attempts=resolved.agent_retry_max_attempts,
        agent_retry_initial_wait_seconds=resolved.agent_retry_initial_wait_seconds,
        agent_retry_max_wait_seconds=resolved.agent_retry_max_wait_seconds,
        agent_retry_backoff_multiplier=resolved.agent_retry_backoff_multiplier,
        agent_max_image_size_bytes=resolved.agent_max_image_size_bytes,
        agent_max_images_per_message=resolved.agent_max_images_per_message,
        agent_base_url=resolved.agent_base_url,
        agent_api_key="***masked***" if resolved.agent_api_key else None,
        overrides=RuntimeSettingsOverridesRead(
            current_user_name=_normalize_optional_text(override.current_user_name)
            if override
            else None,
            user_memory=_normalize_optional_multiline_text(override.user_memory)
            if override
            else None,
            default_currency_code=_normalize_optional_currency(
                override.default_currency_code
            )
            if override
            else None,
            dashboard_currency_code=_normalize_optional_currency(
                override.dashboard_currency_code
            )
            if override
            else None,
            agent_model=_normalize_optional_text(override.agent_model)
            if override
            else None,
            agent_max_steps=override.agent_max_steps if override else None,
            agent_retry_max_attempts=override.agent_retry_max_attempts
            if override
            else None,
            agent_retry_initial_wait_seconds=override.agent_retry_initial_wait_seconds
            if override
            else None,
            agent_retry_max_wait_seconds=override.agent_retry_max_wait_seconds
            if override
            else None,
            agent_retry_backoff_multiplier=override.agent_retry_backoff_multiplier
            if override
            else None,
            agent_max_image_size_bytes=override.agent_max_image_size_bytes
            if override
            else None,
            agent_max_images_per_message=override.agent_max_images_per_message
            if override
            else None,
            agent_base_url=_normalize_optional_text(override.agent_base_url)
            if override
            else None,
            agent_api_key="***masked***"
            if override and override.agent_api_key
            else None,
        ),
    )
