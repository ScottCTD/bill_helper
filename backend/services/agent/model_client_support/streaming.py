# CALLING SPEC:
# - Purpose: implement focused service logic for `streaming`.
# - Inputs: callers that import `backend/services/agent/model_client_support/streaming.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `streaming`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from litellm import APIError

from .usage import coerce_index, coerce_text, read_attr

_TRANSIENT_SSL_BAD_RECORD_MAC_MARKERS = (
    "sslv3_alert_bad_record_mac",
    "sslv3 alert bad record mac",
    "bad record mac",
)


def is_transient_ssl_bad_record_mac_error(exc: Exception) -> bool:
    if not isinstance(exc, APIError):
        return False
    error_text_parts = [str(exc)]
    message = getattr(exc, "message", None)
    if isinstance(message, str):
        error_text_parts.append(message)
    normalized = " ".join(error_text_parts).lower()
    return any(marker in normalized for marker in _TRANSIENT_SSL_BAD_RECORD_MAC_MARKERS)


def append_stream_content(
    *,
    emitted_content: str,
    attempt_content: str,
    content_delta: str,
) -> tuple[str, str, str | None]:
    attempt_content = f"{attempt_content}{content_delta}"
    if attempt_content.startswith(emitted_content):
        suffix = attempt_content[len(emitted_content) :]
        if not suffix:
            return emitted_content, attempt_content, None
        return attempt_content, attempt_content, suffix
    if emitted_content.startswith(attempt_content):
        # Retry replaying an already-emitted prefix; suppress duplicates.
        return emitted_content, attempt_content, None
    raise RuntimeError("model request failed: stream retry produced divergent output")


def finalize_stream_content(
    *,
    emitted_content: str,
    attempt_content: str,
) -> tuple[str, str, str | None]:
    if not attempt_content and emitted_content:
        return emitted_content, emitted_content, None
    if attempt_content.startswith(emitted_content):
        suffix = attempt_content[len(emitted_content) :]
        if not suffix:
            return emitted_content, attempt_content, None
        return attempt_content, attempt_content, suffix
    return emitted_content, emitted_content, None


def merge_streamed_tool_call_fragment(current: str, delta: str) -> str:
    if not current:
        return delta
    if not delta:
        return current
    if delta.startswith(current):
        return delta
    if current.startswith(delta):
        return current
    return f"{current}{delta}"


def merge_tool_call_delta(
    *,
    tool_calls_by_index: dict[int, dict[str, Any]],
    tool_call_delta: Any,
) -> None:
    index = coerce_index(read_attr(tool_call_delta, "index"))
    if index is None:
        return

    current = tool_calls_by_index.setdefault(
        index,
        {
            "id": "",
            "type": "function",
            "function": {"name": "", "arguments": ""},
        },
    )

    delta_id = coerce_text(read_attr(tool_call_delta, "id"))
    if delta_id is not None and not current["id"]:
        current["id"] = delta_id

    delta_type = coerce_text(read_attr(tool_call_delta, "type"))
    if delta_type is not None:
        current["type"] = delta_type

    delta_function = read_attr(tool_call_delta, "function")
    delta_name = coerce_text(read_attr(delta_function, "name"))
    if delta_name is not None:
        current["function"]["name"] = merge_streamed_tool_call_fragment(
            current["function"]["name"],
            delta_name,
        )

    delta_arguments = coerce_text(read_attr(delta_function, "arguments"))
    if delta_arguments is not None:
        current["function"]["arguments"] = merge_streamed_tool_call_fragment(
            current["function"]["arguments"],
            delta_arguments,
        )


def ordered_tool_calls(tool_calls_by_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool_calls_by_index[index] for index in sorted(tool_calls_by_index)]
