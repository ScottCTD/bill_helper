# CALLING SPEC:
# - Purpose: implement focused service logic for `environment`.
# - Inputs: callers that import `backend/services/agent/model_client_support/environment.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `environment`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

import os
from typing import Any

import litellm

from backend.config import DEFAULT_AGENT_MODEL, ensure_env_file_variables_loaded
from backend.services.agent.error_policy import recoverable_result

PROMPT_CACHE_SUPPORT_EXCEPTIONS = (
    AttributeError,
    KeyError,
    RuntimeError,
    TypeError,
    ValueError,
)
ENV_VALIDATION_EXCEPTIONS = (
    AttributeError,
    KeyError,
    RuntimeError,
    TypeError,
    ValueError,
)
_BEDROCK_AUTH_ENV_NAME = "AWS_BEARER_TOKEN_BEDROCK"


def normalize_secret(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def normalize_host(value: Any) -> str | None:
    normalized = normalize_secret(value)
    if normalized is None:
        return None
    return normalized.rstrip("/")


def provider_name_for_model(model_name: str) -> str:
    normalized_model = (model_name or "").strip()
    if not normalized_model:
        return ""
    return normalized_model.split("/", 1)[0].lower()


def supports_prompt_caching(model_name: str) -> bool:
    try:
        return bool(litellm.utils.supports_prompt_caching(model_name))
    except PROMPT_CACHE_SUPPORT_EXCEPTIONS as exc:
        recoverable_result(
            scope="model_client.supports_prompt_caching",
            fallback=False,
            error=exc,
            context={"model_name": model_name},
        )
        return False


def validate_litellm_environment(*, model_name: str) -> tuple[bool, list[str], str]:
    normalized_model = (model_name or "").strip() or DEFAULT_AGENT_MODEL
    provider_name = provider_name_for_model(normalized_model)
    ensure_env_file_variables_loaded()
    try:
        validation = litellm.validate_environment(
            model=normalized_model,
        )
    except ENV_VALIDATION_EXCEPTIONS as exc:
        recoverable_result(
            scope="model_client.validate_environment",
            fallback=None,
            error=exc,
            context={"model_name": normalized_model},
        )
        # Keep fail-fast only when we can confidently determine missing credentials.
        return True, [], normalized_model

    if not isinstance(validation, dict):
        return True, [], normalized_model

    keys_in_environment = validation.get("keys_in_environment")
    if keys_in_environment is not True and keys_in_environment is not False:
        return True, [], normalized_model

    raw_missing = validation.get("missing_keys")
    if isinstance(raw_missing, (list, tuple)):
        missing_keys = [str(value) for value in raw_missing if str(value).strip()]
    else:
        missing_keys = []
    if provider_name == "bedrock":
        if normalize_secret(os.environ.get(_BEDROCK_AUTH_ENV_NAME)) is not None:
            return True, [], normalized_model
        if _BEDROCK_AUTH_ENV_NAME not in missing_keys:
            missing_keys.append(_BEDROCK_AUTH_ENV_NAME)
    return bool(keys_in_environment), missing_keys, normalized_model
