from __future__ import annotations

import json
from typing import Any


USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    try:
        return dict(raw_arguments)
    except (TypeError, ValueError):
        return {}


def decode_tool_call(tool_call: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    function = tool_call.get("function") or {}
    tool_name = str(function.get("name") or "")
    arguments = parse_tool_arguments(function.get("arguments") or "{}")
    return tool_name, arguments


def coerce_usage_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def extract_usage_dict(
    response_message: dict[str, Any],
    *,
    fields: tuple[str, ...] = USAGE_FIELDS,
) -> dict[str, int | None]:
    usage = response_message.get("usage")
    if not isinstance(usage, dict):
        return {field: None for field in fields}
    return {field: coerce_usage_int(usage.get(field)) for field in fields}


def accumulate_usage_totals(
    totals: dict[str, int | None],
    usage: dict[str, int | None],
    *,
    fields: tuple[str, ...] = USAGE_FIELDS,
) -> None:
    for field in fields:
        value = usage.get(field)
        if value is None:
            continue
        current = totals.get(field)
        totals[field] = value if current is None else current + value
