# CALLING SPEC:
# - Purpose: provide the `runtime_settings` module.
# - Inputs: callers that import `backend/validation/runtime_settings.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `runtime_settings`.
# - Side effects: module-local behavior only.
from __future__ import annotations

import json
from collections.abc import Iterable
from ipaddress import ip_address
from urllib.parse import urlparse

from backend.config import DEFAULT_AGENT_MODEL

USER_MEMORY_MAX_CHARS = 4000
_USER_MEMORY_LIST_PREFIXES = ("- ", "* ", "+ ")


def normalize_text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def normalize_multiline_text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()
    return normalized or None


def normalize_user_memory_item_or_none(value: str | None) -> str | None:
    normalized = normalize_text_or_none(value)
    if normalized is None:
        return None
    for prefix in _USER_MEMORY_LIST_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalize_text_or_none(normalized.removeprefix(prefix))
            break
    return normalized or None


def normalize_user_memory_items_or_none(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    normalized_items: list[str] = []
    seen_keys: set[str] = set()
    for raw_value in values:
        item = normalize_user_memory_item_or_none(raw_value)
        if item is None:
            continue
        item_key = item.casefold()
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        normalized_items.append(item)
    return normalized_items or None


def parse_user_memory_or_none(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return normalize_user_memory_items_or_none(str(item) for item in value)
    if isinstance(value, str):
        normalized_text = normalize_multiline_text_or_none(value)
        if normalized_text is None:
            return None
        try:
            decoded = json.loads(normalized_text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return normalize_user_memory_items_or_none(str(item) for item in decoded)
        return normalize_user_memory_items_or_none([normalized_text])
    return normalize_user_memory_items_or_none([str(value)])


def validate_user_memory_size(items: list[str] | None) -> list[str] | None:
    if items is None:
        return None
    if len("\n".join(items)) > USER_MEMORY_MAX_CHARS:
        raise ValueError(f"user_memory must be at most {USER_MEMORY_MAX_CHARS} characters total")
    return items


def serialize_user_memory_or_none(items: list[str] | None) -> str | None:
    normalized_items = validate_user_memory_size(normalize_user_memory_items_or_none(items))
    if normalized_items is None:
        return None
    return json.dumps(normalized_items, ensure_ascii=False)


def normalize_agent_model_item_or_none(value: str | None) -> str | None:
    return normalize_text_or_none(value)


def normalize_agent_model_items_or_none(values: Iterable[str] | None) -> list[str] | None:
    if values is None:
        return None
    normalized_items: list[str] = []
    seen_keys: set[str] = set()
    for raw_value in values:
        item = normalize_agent_model_item_or_none(raw_value)
        if item is None:
            continue
        item_key = item.casefold()
        if item_key in seen_keys:
            continue
        seen_keys.add(item_key)
        normalized_items.append(item)
    return normalized_items or None


def parse_agent_models_or_none(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return normalize_agent_model_items_or_none(str(item) for item in value)
    if isinstance(value, str):
        normalized_text = normalize_multiline_text_or_none(value)
        if normalized_text is None:
            return None
        try:
            decoded = json.loads(normalized_text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            return normalize_agent_model_items_or_none(str(item) for item in decoded)
        return normalize_agent_model_items_or_none(normalized_text.split("\n"))
    return normalize_agent_model_items_or_none([str(value)])


def serialize_agent_models_or_none(items: list[str] | None) -> str | None:
    normalized_items = normalize_agent_model_items_or_none(items)
    if normalized_items is None:
        return None
    return json.dumps(normalized_items, ensure_ascii=False)


AGENT_MODEL_DISPLAY_NAME_MAX_LEN = 80
AGENT_MODEL_DISPLAY_NAMES_MAX_KEYS = 64

# Built-in labels for the default available-model catalog (case-insensitive match on id).
# User-stored overrides in `agent_model_display_names` replace these per model id.
STANDARD_AGENT_MODEL_DISPLAY_NAMES: dict[str, str] = {
    DEFAULT_AGENT_MODEL: "Claude Haiku 4.5",
    "bedrock/us.anthropic.claude-sonnet-4-6": "Claude Sonnet 4.6",
    "openrouter/qwen/qwen3.5-27b": "Qwen 3.5 27B",
    "openrouter/moonshotai/kimi-k2.5": "Kimi K2.5",
    "openrouter/minimax/minimax-m2.5": "MiniMax 2.5",
}
_STANDARD_LABELS_BY_CASEFOLD: dict[str, str] = {
    key.casefold(): label for key, label in STANDARD_AGENT_MODEL_DISPLAY_NAMES.items()
}


def normalize_agent_model_display_names_payload_or_none(
    value: object | None,
) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("agent_model_display_names must be a JSON object or null")
    normalized: dict[str, str] = {}
    seen_keys: set[str] = set()
    for raw_key, raw_val in value.items():
        key = normalize_agent_model_item_or_none(str(raw_key))
        if key is None:
            continue
        key_fold = key.casefold()
        if key_fold in seen_keys:
            continue
        seen_keys.add(key_fold)
        val = normalize_text_or_none(str(raw_val))
        if val is None:
            continue
        if len(val) > AGENT_MODEL_DISPLAY_NAME_MAX_LEN:
            raise ValueError(
                f"agent_model_display_names values must be at most {AGENT_MODEL_DISPLAY_NAME_MAX_LEN} characters"
            )
        normalized[key] = val
        if len(normalized) > AGENT_MODEL_DISPLAY_NAMES_MAX_KEYS:
            raise ValueError(
                f"agent_model_display_names must have at most {AGENT_MODEL_DISPLAY_NAMES_MAX_KEYS} entries"
            )
    return normalized or None


def parse_agent_model_display_names_or_none(value: object) -> dict[str, str] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return normalize_agent_model_display_names_payload_or_none(value)
    if isinstance(value, str):
        normalized_text = normalize_multiline_text_or_none(value)
        if normalized_text is None:
            return None
        try:
            decoded = json.loads(normalized_text)
        except json.JSONDecodeError:
            return None
        if isinstance(decoded, dict):
            return normalize_agent_model_display_names_payload_or_none(decoded)
        return None
    return None


def finalize_agent_model_display_names_for_storage(
    payload: dict[str, str] | None,
    *,
    available_agent_models: list[str],
) -> str | None:
    if not payload:
        return None
    available_by_fold = {model.casefold(): model for model in available_agent_models}
    merged: dict[str, str] = {}
    for raw_key, raw_val in payload.items():
        key = normalize_agent_model_item_or_none(raw_key)
        if key is None:
            continue
        canonical = available_by_fold.get(key.casefold())
        if canonical is None:
            continue
        val = normalize_text_or_none(str(raw_val))
        if val is None:
            continue
        merged[canonical] = val[:AGENT_MODEL_DISPLAY_NAME_MAX_LEN]
    if not merged:
        return None
    return json.dumps(merged, ensure_ascii=False)


def build_effective_agent_model_display_names(
    *,
    available_agent_models: list[str],
    stored_text: str | None,
) -> dict[str, str]:
    stored = parse_agent_model_display_names_or_none(stored_text) if stored_text else None
    available_by_fold = {model.casefold(): model for model in available_agent_models}
    out: dict[str, str] = {}
    for canonical in available_agent_models:
        label = _STANDARD_LABELS_BY_CASEFOLD.get(canonical.casefold())
        if label:
            out[canonical] = label
    if stored:
        for key, val in stored.items():
            canonical = available_by_fold.get(key.casefold())
            if canonical is None:
                continue
            val_norm = normalize_text_or_none(val)
            if val_norm is None:
                continue
            out[canonical] = val_norm
    return out


def normalize_currency_code_or_none(value: str | None) -> str | None:
    normalized = normalize_text_or_none(value)
    if normalized is None:
        return None
    code = normalized.upper()
    if len(code) != 3:
        return None
    return code


def normalize_secret_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def sanitize_int_at_least(value: int, *, minimum: int, fallback: int) -> int:
    if value < minimum:
        return max(fallback, minimum)
    return value


def sanitize_int_between(value: int, *, minimum: int, maximum: int, fallback: int) -> int:
    if value < minimum:
        return min(max(fallback, minimum), maximum)
    if value > maximum:
        return min(max(fallback, minimum), maximum)
    return value


def sanitize_float_at_least(value: float, *, minimum: float, fallback: float) -> float:
    if value < minimum:
        return max(fallback, minimum)
    return value


def validate_agent_base_url_or_none(value: str | None) -> str | None:
    normalized = normalize_text_or_none(value)
    if normalized is None:
        return None
    parsed = urlparse(normalized)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("agent_base_url must use http or https scheme")
    if not parsed.netloc:
        raise ValueError("agent_base_url must have a valid host")
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise ValueError("agent_base_url must have a valid host")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("agent_base_url cannot point to localhost hosts")

    try:
        host_ip = ip_address(hostname)
    except ValueError:
        return normalized

    if (
        host_ip.is_private
        or host_ip.is_loopback
        or host_ip.is_link_local
        or host_ip.is_reserved
        or host_ip.is_multicast
        or host_ip.is_unspecified
    ):
        raise ValueError("agent_base_url cannot point to non-public IP addresses")
    return normalized


def validate_agent_api_key_or_none(value: str | None) -> str | None:
    normalized = normalize_secret_or_none(value)
    if normalized is None:
        return None
    if normalized == "***masked***":
        raise ValueError("agent_api_key cannot be the masked sentinel value")
    return normalized
