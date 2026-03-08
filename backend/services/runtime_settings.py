from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import DEFAULT_AGENT_MODEL, get_settings
from backend.models_finance import RuntimeSettings as RuntimeSettingsRow
from backend.schemas_finance import RuntimeSettingsOverridesRead, RuntimeSettingsRead, RuntimeSettingsUpdate
from backend.services.agent.model_client import validate_litellm_environment
from backend.services.runtime_settings_normalization import (
    parse_agent_models_or_none,
    normalize_currency_code_or_none,
    parse_user_memory_or_none,
    normalize_secret_or_none,
    normalize_text_or_none,
    sanitize_float_at_least,
    sanitize_int_at_least,
    sanitize_int_between,
    serialize_agent_models_or_none,
    serialize_user_memory_or_none,
    validate_user_memory_size,
)

RUNTIME_SETTINGS_SCOPE = "default"
DEFAULT_AVAILABLE_AGENT_MODELS = (
    DEFAULT_AGENT_MODEL,
    "openai/gpt-4.1-mini",
    "openrouter/qwen/qwen3.5-27b",
)


@dataclass(slots=True, frozen=True)
class ResolvedRuntimeSettings:
    api_prefix: str
    current_user_name: str
    user_memory: list[str] | None
    default_currency_code: str
    dashboard_currency_code: str
    agent_model: str
    available_agent_models: list[str]
    agent_max_steps: int
    agent_bulk_max_concurrent_threads: int
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
    db: Session,
    updates: RuntimeSettingsUpdate,
) -> RuntimeSettingsRow:
    row = _ensure_runtime_settings_override(db)
    for field_name, value in updates.model_dump(exclude_unset=True).items():
        # Skip masked sentinel to prevent accidental overwrites of API key
        if field_name == "agent_api_key" and value == "***masked***":
            continue
        if field_name == "available_agent_models":
            value = serialize_agent_models_or_none(value)
        if field_name == "user_memory":
            value = serialize_user_memory_or_none(value)
        setattr(row, field_name, value)
    db.add(row)
    db.flush()
    return row


def append_user_memory_items(
    db: Session,
    *,
    items: list[str],
) -> tuple[list[str], list[str]]:
    normalized_items = validate_user_memory_size(items)
    if not normalized_items:
        raise ValueError("user memory items cannot be empty")

    row = _ensure_runtime_settings_override(db)
    existing_items = parse_user_memory_or_none(row.user_memory) or []
    seen_keys = {item.casefold() for item in existing_items}

    added_items: list[str] = []
    merged_items = list(existing_items)
    for item in normalized_items:
        item_key = item.casefold()
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        merged_items.append(item)
        added_items.append(item)

    row.user_memory = serialize_user_memory_or_none(merged_items)
    db.add(row)
    db.flush()
    return added_items, merged_items


def _default_available_agent_models() -> list[str]:
    return list(parse_agent_models_or_none(DEFAULT_AVAILABLE_AGENT_MODELS) or [DEFAULT_AGENT_MODEL])


def _ensure_available_models_include_default(
    available_models: list[str] | None,
    *,
    agent_model: str,
) -> list[str]:
    normalized_models = list(available_models or _default_available_agent_models())
    if agent_model.casefold() in {model.casefold() for model in normalized_models}:
        return normalized_models
    return [*normalized_models, agent_model]


def resolve_runtime_settings(db: Session) -> ResolvedRuntimeSettings:
    defaults = get_settings()
    override = get_runtime_settings_override(db)

    current_user_name = (
        normalize_text_or_none(defaults.current_user_name)
        or "admin"
    )
    user_memory = (
        parse_user_memory_or_none(override.user_memory)
        if override is not None
        else None
    )
    default_currency_code = (
        (
            normalize_currency_code_or_none(override.default_currency_code)
            if override is not None
            else None
        )
        or normalize_currency_code_or_none(defaults.default_currency_code)
        or "CAD"
    )
    dashboard_currency_code = (
        (
            normalize_currency_code_or_none(override.dashboard_currency_code)
            if override is not None
            else None
        )
        or normalize_currency_code_or_none(defaults.dashboard_currency_code)
        or "CAD"
    )
    agent_model = (
        (
            normalize_text_or_none(override.agent_model)
            if override is not None
            else None
        )
        or normalize_text_or_none(defaults.agent_model)
        or DEFAULT_AGENT_MODEL
    )
    available_agent_models = _ensure_available_models_include_default(
        parse_agent_models_or_none(override.available_agent_models)
        if override is not None
        else None,
        agent_model=agent_model,
    )

    agent_max_steps = sanitize_int_at_least(
        override.agent_max_steps
        if override and override.agent_max_steps is not None
        else defaults.agent_max_steps,
        minimum=1,
        fallback=defaults.agent_max_steps,
    )
    agent_bulk_max_concurrent_threads = sanitize_int_between(
        override.agent_bulk_max_concurrent_threads
        if override and override.agent_bulk_max_concurrent_threads is not None
        else defaults.agent_bulk_max_concurrent_threads,
        minimum=1,
        maximum=16,
        fallback=defaults.agent_bulk_max_concurrent_threads,
    )
    agent_retry_max_attempts = sanitize_int_at_least(
        override.agent_retry_max_attempts
        if override and override.agent_retry_max_attempts is not None
        else defaults.agent_retry_max_attempts,
        minimum=1,
        fallback=defaults.agent_retry_max_attempts,
    )
    agent_retry_initial_wait_seconds = sanitize_float_at_least(
        override.agent_retry_initial_wait_seconds
        if override and override.agent_retry_initial_wait_seconds is not None
        else defaults.agent_retry_initial_wait_seconds,
        minimum=0.0,
        fallback=defaults.agent_retry_initial_wait_seconds,
    )
    agent_retry_max_wait_seconds = sanitize_float_at_least(
        override.agent_retry_max_wait_seconds
        if override and override.agent_retry_max_wait_seconds is not None
        else defaults.agent_retry_max_wait_seconds,
        minimum=0.0,
        fallback=defaults.agent_retry_max_wait_seconds,
    )
    agent_retry_backoff_multiplier = sanitize_float_at_least(
        override.agent_retry_backoff_multiplier
        if override and override.agent_retry_backoff_multiplier is not None
        else defaults.agent_retry_backoff_multiplier,
        minimum=1.0,
        fallback=defaults.agent_retry_backoff_multiplier,
    )
    agent_max_image_size_bytes = sanitize_int_at_least(
        override.agent_max_image_size_bytes
        if override and override.agent_max_image_size_bytes is not None
        else defaults.agent_max_image_size_bytes,
        minimum=1024,
        fallback=defaults.agent_max_image_size_bytes,
    )
    agent_max_images_per_message = sanitize_int_at_least(
        override.agent_max_images_per_message
        if override and override.agent_max_images_per_message is not None
        else defaults.agent_max_images_per_message,
        minimum=1,
        fallback=defaults.agent_max_images_per_message,
    )
    agent_base_url = (
        normalize_text_or_none(override.agent_base_url if override else None)
    ) or normalize_text_or_none(defaults.agent_base_url)
    agent_api_key = (
        normalize_secret_or_none(override.agent_api_key if override else None)
    ) or normalize_secret_or_none(defaults.agent_api_key)

    return ResolvedRuntimeSettings(
        api_prefix=defaults.api_prefix,
        current_user_name=current_user_name,
        user_memory=user_memory,
        default_currency_code=default_currency_code,
        dashboard_currency_code=dashboard_currency_code,
        agent_model=agent_model,
        available_agent_models=available_agent_models,
        agent_max_steps=agent_max_steps,
        agent_bulk_max_concurrent_threads=agent_bulk_max_concurrent_threads,
        agent_retry_max_attempts=agent_retry_max_attempts,
        agent_retry_initial_wait_seconds=agent_retry_initial_wait_seconds,
        agent_retry_max_wait_seconds=agent_retry_max_wait_seconds,
        agent_retry_backoff_multiplier=agent_retry_backoff_multiplier,
        agent_max_image_size_bytes=agent_max_image_size_bytes,
        agent_max_images_per_message=agent_max_images_per_message,
        agent_base_url=agent_base_url,
        agent_api_key=agent_api_key,
    )


def build_runtime_settings_read(
    db: Session,
    *,
    principal_name: str | None = None,
) -> RuntimeSettingsRead:
    override = get_runtime_settings_override(db)
    resolved = resolve_runtime_settings(db)
    has_provider_credentials, _, _ = validate_litellm_environment(
        model_name=resolved.agent_model
    )

    return RuntimeSettingsRead(
        current_user_name=normalize_text_or_none(principal_name) or resolved.current_user_name,
        user_memory=resolved.user_memory,
        default_currency_code=resolved.default_currency_code,
        dashboard_currency_code=resolved.dashboard_currency_code,
        agent_model=resolved.agent_model,
        available_agent_models=resolved.available_agent_models,
        agent_max_steps=resolved.agent_max_steps,
        agent_bulk_max_concurrent_threads=resolved.agent_bulk_max_concurrent_threads,
        agent_retry_max_attempts=resolved.agent_retry_max_attempts,
        agent_retry_initial_wait_seconds=resolved.agent_retry_initial_wait_seconds,
        agent_retry_max_wait_seconds=resolved.agent_retry_max_wait_seconds,
        agent_retry_backoff_multiplier=resolved.agent_retry_backoff_multiplier,
        agent_max_image_size_bytes=resolved.agent_max_image_size_bytes,
        agent_max_images_per_message=resolved.agent_max_images_per_message,
        agent_base_url=resolved.agent_base_url,
        agent_api_key_configured=bool(resolved.agent_api_key) or has_provider_credentials,
        overrides=RuntimeSettingsOverridesRead(
            user_memory=parse_user_memory_or_none(override.user_memory)
            if override
            else None,
            default_currency_code=normalize_currency_code_or_none(
                override.default_currency_code
            )
            if override
            else None,
            dashboard_currency_code=normalize_currency_code_or_none(
                override.dashboard_currency_code
            )
            if override
            else None,
            agent_model=normalize_text_or_none(override.agent_model)
            if override
            else None,
            available_agent_models=parse_agent_models_or_none(override.available_agent_models)
            if override
            else None,
            agent_max_steps=override.agent_max_steps if override else None,
            agent_bulk_max_concurrent_threads=override.agent_bulk_max_concurrent_threads
            if override
            else None,
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
            agent_base_url=normalize_text_or_none(override.agent_base_url)
            if override
            else None,
            agent_api_key_configured=bool(override and override.agent_api_key),
        ),
    )
