from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


def _coerce_argument_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    try:
        return dict(value)
    except (TypeError, ValueError):
        return None


def _strip_code_fences(raw_arguments: str) -> str:
    candidate = raw_arguments.strip()
    if not (candidate.startswith("```") and candidate.endswith("```")):
        return candidate
    lines = candidate.splitlines()
    if len(lines) < 3:
        return candidate
    return "\n".join(lines[1:-1]).strip()


def parse_tool_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, str):
        candidate = _strip_code_fences(raw_arguments)
        for _ in range(3):
            try:
                parsed = json.loads(candidate)
            except (TypeError, ValueError):
                return {}
            coerced = _coerce_argument_mapping(parsed)
            if coerced is not None:
                return coerced
            if isinstance(parsed, str):
                candidate = _strip_code_fences(parsed)
                continue
            return {}
        return {}

    coerced = _coerce_argument_mapping(raw_arguments)
    return coerced if coerced is not None else {}


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
