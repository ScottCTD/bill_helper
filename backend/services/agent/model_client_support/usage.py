from __future__ import annotations

from typing import Any


def read_attr(source: Any, key: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def read_int(source: Any, key: str) -> int | None:
    value = read_attr(source, key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def coerce_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value if value else None


def coerce_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def normalize_usage(usage: Any) -> dict[str, int | None]:
    prompt_details = read_attr(usage, "prompt_tokens_details")
    input_tokens = read_int(usage, "input_tokens")
    if input_tokens is None:
        input_tokens = read_int(usage, "prompt_tokens")

    output_tokens = read_int(usage, "output_tokens")
    if output_tokens is None:
        output_tokens = read_int(usage, "completion_tokens")

    cache_read_tokens = read_int(usage, "cache_read_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = read_int(usage, "cache_read_input_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = read_int(usage, "cached_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = read_int(prompt_details, "cache_read_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = read_int(prompt_details, "cache_read_input_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = read_int(prompt_details, "cached_tokens")

    cache_write_tokens = read_int(usage, "cache_write_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = read_int(usage, "cache_creation_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = read_int(usage, "cache_creation_input_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = read_int(prompt_details, "cache_write_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = read_int(prompt_details, "cache_creation_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = read_int(prompt_details, "cache_creation_input_tokens")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }


def empty_usage_totals() -> dict[str, int | None]:
    return {
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
    }


def apply_usage_totals(
    usage_totals: dict[str, int | None],
    usage: dict[str, int | None],
) -> None:
    for field, value in usage.items():
        if value is not None:
            usage_totals[field] = value
