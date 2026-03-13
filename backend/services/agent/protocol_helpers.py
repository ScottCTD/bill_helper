# CALLING SPEC:
# - Purpose: implement focused service logic for `protocol_helpers`.
# - Inputs: callers that import `backend/services/agent/protocol_helpers.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `protocol_helpers`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
import json
from collections.abc import Mapping
from typing import Any

from backend.services.agent.tool_types import ToolExecutionResult, ToolExecutionStatus


USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


@dataclass(frozen=True, slots=True)
class ParsedToolArguments:
    arguments: dict[str, Any]
    raw_arguments: str | None = None
    decode_error: str | None = None


@dataclass(frozen=True, slots=True)
class DecodedToolCall:
    tool_name: str
    arguments: dict[str, Any]
    raw_arguments: str | None = None
    decode_error: str | None = None


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


def _raw_argument_text(raw_arguments: Any) -> str:
    if isinstance(raw_arguments, str):
        return raw_arguments
    try:
        return json.dumps(raw_arguments, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(raw_arguments)


def parse_tool_arguments(raw_arguments: Any) -> ParsedToolArguments:
    if isinstance(raw_arguments, str):
        candidate = _strip_code_fences(raw_arguments)
        for _ in range(3):
            try:
                parsed = json.loads(candidate)
            except (TypeError, ValueError):
                return ParsedToolArguments(
                    arguments={},
                    raw_arguments=raw_arguments,
                    decode_error="arguments are not valid JSON",
                )
            coerced = _coerce_argument_mapping(parsed)
            if coerced is not None:
                return ParsedToolArguments(arguments=coerced, raw_arguments=raw_arguments)
            if isinstance(parsed, str):
                candidate = _strip_code_fences(parsed)
                continue
            return ParsedToolArguments(
                arguments={},
                raw_arguments=raw_arguments,
                decode_error="arguments must decode to a JSON object",
            )
        return ParsedToolArguments(
            arguments={},
            raw_arguments=raw_arguments,
            decode_error="arguments exceeded nested JSON string decode limit",
        )

    coerced = _coerce_argument_mapping(raw_arguments)
    if coerced is not None:
        return ParsedToolArguments(arguments=coerced)
    return ParsedToolArguments(
        arguments={},
        raw_arguments=_raw_argument_text(raw_arguments),
        decode_error="arguments must be an object or JSON object string",
    )


def decode_tool_call(tool_call: dict[str, Any]) -> DecodedToolCall:
    function = tool_call.get("function") or {}
    tool_name = str(function.get("name") or "")
    parsed = parse_tool_arguments(
        "{}" if function.get("arguments") is None else function.get("arguments")
    )
    return DecodedToolCall(
        tool_name=tool_name,
        arguments=parsed.arguments,
        raw_arguments=parsed.raw_arguments,
        decode_error=parsed.decode_error,
    )


def canonicalize_tool_call(tool_call: dict[str, Any]) -> dict[str, Any]:
    decoded = decode_tool_call(tool_call)
    serialized_arguments = (
        decoded.raw_arguments
        if decoded.decode_error is not None and decoded.raw_arguments is not None
        else json.dumps(decoded.arguments, separators=(",", ":"))
    )
    return {
        "id": tool_call.get("id"),
        "type": str(tool_call.get("type") or "function"),
        "function": {
            "name": decoded.tool_name,
            "arguments": serialized_arguments,
        },
    }


def tool_call_decode_error_result(
    *,
    tool_name: str,
    raw_arguments: str | None,
    decode_error: str,
) -> ToolExecutionResult:
    details: dict[str, Any] = {
        "tool_name": tool_name,
        "decode_error": decode_error,
    }
    if raw_arguments is not None:
        details["raw_arguments"] = raw_arguments
    summary = "tool argument decode failed"
    return ToolExecutionResult(
        output_text=f"ERROR\nsummary: {summary}\ndetails: {details}",
        output_json={
            "status": "ERROR",
            "summary": summary,
            "details": details,
        },
        status=ToolExecutionStatus.ERROR,
    )


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
