from __future__ import annotations

import json
from collections.abc import Iterable
from ipaddress import ip_address
from urllib.parse import urlparse

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
        return normalize_user_memory_items_or_none(normalized_text.split("\n"))
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
