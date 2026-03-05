from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlparse


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
