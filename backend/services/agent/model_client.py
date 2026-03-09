from __future__ import annotations

from collections.abc import Iterator
import os
from typing import Any

import litellm
from litellm import APIConnectionError, APIError, OpenAIError, Timeout
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import DEFAULT_AGENT_MODEL, ensure_env_file_variables_loaded
from backend.services.agent.error_policy import recoverable_result


class AgentModelError(RuntimeError):
    pass


_TRANSIENT_SSL_BAD_RECORD_MAC_MARKERS = (
    "sslv3_alert_bad_record_mac",
    "sslv3 alert bad record mac",
    "bad record mac",
)
_PROMPT_CACHE_INJECTION_POINTS_MAX = 4
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


def _normalize_secret(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_host(value: Any) -> str | None:
    normalized = _normalize_secret(value)
    if normalized is None:
        return None
    return normalized.rstrip("/")


def _provider_name_for_model(model_name: str) -> str:
    normalized_model = (model_name or "").strip()
    if not normalized_model:
        return ""
    return normalized_model.split("/", 1)[0].lower()


def _is_transient_ssl_bad_record_mac_error(exc: Exception) -> bool:
    if not isinstance(exc, APIError):
        return False
    error_text_parts = [str(exc)]
    message = getattr(exc, "message", None)
    if isinstance(message, str):
        error_text_parts.append(message)
    normalized = " ".join(error_text_parts).lower()
    return any(marker in normalized for marker in _TRANSIENT_SSL_BAD_RECORD_MAC_MARKERS)


def _supports_prompt_caching(model_name: str) -> bool:
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


def _cache_injection_points_for_messages(
    messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # Place breakpoints so every LLM call can READ the previous call's cache
    # and WRITE a new cache for the next call.
    #
    # Tool-loop iteration (last message role == "tool"):
    #   New messages since last call: [assistant(tc), tool, tool, ...]
    #   Boundary = message just before that assistant = previous call's last msg.
    #   Breakpoint there READs the previous call's cache.
    #
    # New user turn (last message role == "user"):
    #   Second-to-last user message = previous turn's initial-call cache endpoint.
    #   Breakpoint there READs the cross-turn cache.
    #
    # Always: system at index 0 (long-lived prefix) + last message (WRITE for next call).
    if len(messages) < 2:
        return []

    n = len(messages)
    points: list[dict[str, Any]] = [
        {"location": "message", "index": 0},
    ]

    last_role = messages[-1].get("role")

    if last_role == "tool":
        # Walk backwards past trailing tool results, then past the assistant.
        i = n - 1
        while i >= 0 and messages[i].get("role") == "tool":
            i -= 1
        if i >= 1 and messages[i].get("role") == "assistant":
            boundary = i - 1
            if boundary > 0:
                points.append({"location": "message", "index": boundary - n})
    elif last_role == "user":
        # Find second-to-last user message for cross-turn cache reuse.
        for i in range(n - 2, -1, -1):
            if messages[i].get("role") == "user":
                points.append({"location": "message", "index": i - n})
                break

    points.append({"location": "message", "index": -1})

    unique_points: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for point in points:
        key = tuple(sorted(point.items()))
        if key in seen:
            continue
        seen.add(key)
        unique_points.append(point)
    return unique_points[:_PROMPT_CACHE_INJECTION_POINTS_MAX]


def _read_attr(source: Any, key: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _read_int(source: Any, key: str) -> int | None:
    value = _read_attr(source, key)
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _normalize_usage(usage: Any) -> dict[str, int | None]:
    prompt_details = _read_attr(usage, "prompt_tokens_details")
    input_tokens = _read_int(usage, "input_tokens")
    if input_tokens is None:
        input_tokens = _read_int(usage, "prompt_tokens")

    output_tokens = _read_int(usage, "output_tokens")
    if output_tokens is None:
        output_tokens = _read_int(usage, "completion_tokens")

    cache_read_tokens = _read_int(usage, "cache_read_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(usage, "cache_read_input_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(usage, "cached_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(prompt_details, "cache_read_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(prompt_details, "cache_read_input_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(prompt_details, "cached_tokens")

    cache_write_tokens = _read_int(usage, "cache_write_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = _read_int(usage, "cache_creation_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = _read_int(usage, "cache_creation_input_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = _read_int(prompt_details, "cache_write_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = _read_int(prompt_details, "cache_creation_tokens")
    if cache_write_tokens is None:
        cache_write_tokens = _read_int(prompt_details, "cache_creation_input_tokens")

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }


def _coerce_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value if value else None


def _coerce_index(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _empty_usage_totals() -> dict[str, int | None]:
    return {
        "input_tokens": None,
        "output_tokens": None,
        "cache_read_tokens": None,
        "cache_write_tokens": None,
    }


def _apply_usage_totals(
    usage_totals: dict[str, int | None],
    usage: dict[str, int | None],
) -> None:
    for field, value in usage.items():
        if value is not None:
            usage_totals[field] = value


def _append_stream_content(
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
    raise AgentModelError(
        "model request failed: stream retry produced divergent output"
    )


def _finalize_stream_content(
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


def _merge_tool_call_delta(
    *,
    tool_calls_by_index: dict[int, dict[str, Any]],
    tool_call_delta: Any,
) -> None:
    index = _coerce_index(_read_attr(tool_call_delta, "index"))
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

    delta_id = _coerce_text(_read_attr(tool_call_delta, "id"))
    if delta_id is not None and not current["id"]:
        current["id"] = delta_id

    delta_type = _coerce_text(_read_attr(tool_call_delta, "type"))
    if delta_type is not None:
        current["type"] = delta_type

    delta_function = _read_attr(tool_call_delta, "function")
    delta_name = _coerce_text(_read_attr(delta_function, "name"))
    if delta_name is not None:
        current["function"]["name"] = _merge_streamed_tool_call_fragment(
            current["function"]["name"],
            delta_name,
        )

    delta_arguments = _coerce_text(_read_attr(delta_function, "arguments"))
    if delta_arguments is not None:
        current["function"]["arguments"] = _merge_streamed_tool_call_fragment(
            current["function"]["arguments"],
            delta_arguments,
        )


def _merge_streamed_tool_call_fragment(current: str, delta: str) -> str:
    if not current:
        return delta
    if not delta:
        return current
    if delta.startswith(current):
        return delta
    if current.startswith(delta):
        return current
    return f"{current}{delta}"


def _ordered_tool_calls(tool_calls_by_index: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [tool_calls_by_index[index] for index in sorted(tool_calls_by_index)]


def validate_litellm_environment(*, model_name: str) -> tuple[bool, list[str], str]:
    normalized_model = (model_name or "").strip() or DEFAULT_AGENT_MODEL
    provider_name = _provider_name_for_model(normalized_model)
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
        if _normalize_secret(os.environ.get(_BEDROCK_AUTH_ENV_NAME)) is not None:
            return True, [], normalized_model
        if _BEDROCK_AUTH_ENV_NAME not in missing_keys:
            missing_keys.append(_BEDROCK_AUTH_ENV_NAME)
    return bool(keys_in_environment), missing_keys, normalized_model


class LiteLLMModelClient:
    def __init__(
        self,
        *,
        model_name: str,
        tools: list[dict[str, Any]],
        retry_max_attempts: int,
        retry_initial_wait_seconds: float,
        retry_max_wait_seconds: float,
        retry_backoff_multiplier: float,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        ensure_env_file_variables_loaded()
        self._model_name = (model_name or "").strip() or DEFAULT_AGENT_MODEL
        self._tools = tools
        self._retry_max_attempts = max(1, retry_max_attempts)
        self._retry_initial_wait_seconds = max(0.0, retry_initial_wait_seconds)
        self._retry_max_wait_seconds = max(0.0, retry_max_wait_seconds)
        self._retry_backoff_multiplier = max(1.0, retry_backoff_multiplier)
        self._base_url = _normalize_host(base_url)
        self._api_key = _normalize_secret(api_key)

    def _base_request(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "tools": self._tools,
            "tool_choice": "auto",
        }
        if _supports_prompt_caching(self._model_name):
            injection_points = _cache_injection_points_for_messages(messages)
            if injection_points:
                request["cache_control_injection_points"] = injection_points

        if self._base_url is not None:
            request["base_url"] = self._base_url
        if self._api_key is not None:
            request["api_key"] = self._api_key
        return request

    def _to_model_error(self, exc: Exception) -> AgentModelError:
        if isinstance(exc, Timeout):
            message = "model request timed out"
        elif isinstance(exc, APIConnectionError):
            message = f"model request failed: {str(exc)}"
        elif isinstance(exc, APIError):
            status_code = getattr(exc, "status_code", None)
            if status_code is not None:
                message_detail = getattr(exc, "message", None) or str(exc)
                message = f"model request failed ({status_code}): {message_detail}"
            else:
                message = f"model request failed: {str(exc)}"
        elif isinstance(exc, OpenAIError):
            status_code = getattr(exc, "status_code", None)
            if status_code is not None:
                message_detail = getattr(exc, "message", None) or str(exc)
                message = f"model request failed ({status_code}): {message_detail}"
            else:
                message = f"model request failed: {str(exc)}"
        else:  # pragma: no cover - defensive guard
            message = f"model request failed: {str(exc)}"
        return AgentModelError(message)

    def _completion_with_transient_ssl_retry(self, request: dict[str, Any]) -> Any:
        try:
            return litellm.completion(**request)
        except Exception as exc:
            if not _is_transient_ssl_bad_record_mac_error(exc):
                raise
            return litellm.completion(**request)

    def _chat_completion_once(
        self,
        messages: list[dict[str, Any]],
    ) -> Any:
        request = self._base_request(messages)
        try:
            return self._completion_with_transient_ssl_retry(request)
        except Exception as exc:
            raise self._to_model_error(exc) from exc

    def _stream_completion_once(self, request: dict[str, Any]) -> Any:
        try:
            return self._completion_with_transient_ssl_retry(request)
        except OpenAIError as exc:
            status_code = getattr(exc, "status_code", None)
            if request.get("stream_options") and status_code in (400, 422):
                # Some OpenAI-compatible providers reject `stream_options`; retry once without it.
                retry_request = {
                    key: value
                    for key, value in request.items()
                    if key != "stream_options"
                }
                return self._completion_with_transient_ssl_retry(retry_request)
            raise

    def complete(
        self,
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        retrying = Retrying(
            stop=stop_after_attempt(self._retry_max_attempts),
            wait=wait_exponential(
                multiplier=self._retry_initial_wait_seconds,
                max=self._retry_max_wait_seconds,
                exp_base=self._retry_backoff_multiplier,
            ),
            retry=retry_if_exception_type(AgentModelError),
            reraise=True,
        )
        response = None
        for attempt in retrying:
            with attempt:
                response = self._chat_completion_once(messages)
        if response is None:  # pragma: no cover - defensive guard
            raise AgentModelError("model request failed: no response")

        try:
            message = response.choices[0].message
        except (IndexError, AttributeError) as exc:
            raise AgentModelError("model response was malformed") from exc

        tool_calls = []
        for call in message.tool_calls or []:
            tool_calls.append(
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
            )

        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": tool_calls,
            "usage": _normalize_usage(getattr(response, "usage", None)),
        }

    def complete_stream(
        self,
        messages: list[dict[str, Any]],
    ) -> Iterator[dict[str, Any]]:
        request = self._base_request(messages)
        request["stream"] = True
        request["stream_options"] = {"include_usage": True}

        emitted_content = ""
        final_content = ""
        emitted_reasoning = ""
        final_reasoning = ""
        usage_totals = _empty_usage_totals()
        final_tool_calls_by_index: dict[int, dict[str, Any]] = {}

        retrying = Retrying(
            stop=stop_after_attempt(self._retry_max_attempts),
            wait=wait_exponential(
                multiplier=self._retry_initial_wait_seconds,
                max=self._retry_max_wait_seconds,
                exp_base=self._retry_backoff_multiplier,
            ),
            retry=retry_if_exception_type(AgentModelError),
            reraise=True,
        )

        for attempt in retrying:
            with attempt:
                try:
                    stream = self._stream_completion_once(request)
                    attempt_content = ""
                    attempt_reasoning = ""
                    attempt_tool_calls_by_index: dict[int, dict[str, Any]] = {}
                    for chunk in stream:
                        _apply_usage_totals(
                            usage_totals,
                            _normalize_usage(_read_attr(chunk, "usage")),
                        )

                        choices = _read_attr(chunk, "choices") or []
                        for choice in choices:
                            delta = _read_attr(choice, "delta")
                            if delta is None:
                                continue

                            reasoning_delta = _coerce_text(
                                _read_attr(delta, "reasoning_content")
                            ) or _coerce_text(_read_attr(delta, "reasoning"))
                            if reasoning_delta is not None:
                                emitted_reasoning, attempt_reasoning, streamed_reasoning_delta = (
                                    _append_stream_content(
                                        emitted_content=emitted_reasoning,
                                        attempt_content=attempt_reasoning,
                                        content_delta=reasoning_delta,
                                    )
                                )
                                if streamed_reasoning_delta is not None:
                                    yield {
                                        "type": "reasoning_delta",
                                        "delta": streamed_reasoning_delta,
                                    }

                            content_delta = _coerce_text(_read_attr(delta, "content"))
                            if content_delta is not None:
                                emitted_content, attempt_content, text_delta = (
                                    _append_stream_content(
                                        emitted_content=emitted_content,
                                        attempt_content=attempt_content,
                                        content_delta=content_delta,
                                    )
                                )
                                if text_delta is not None:
                                    yield {"type": "text_delta", "delta": text_delta}

                            for tool_call_delta in _read_attr(delta, "tool_calls") or []:
                                _merge_tool_call_delta(
                                    tool_calls_by_index=attempt_tool_calls_by_index,
                                    tool_call_delta=tool_call_delta,
                                )

                    emitted_content, final_content, trailing_delta = (
                        _finalize_stream_content(
                            emitted_content=emitted_content,
                            attempt_content=attempt_content,
                        )
                    )
                    if trailing_delta is not None:
                        yield {"type": "text_delta", "delta": trailing_delta}
                    emitted_reasoning, final_reasoning, trailing_reasoning_delta = (
                        _finalize_stream_content(
                            emitted_content=emitted_reasoning,
                            attempt_content=attempt_reasoning,
                        )
                    )
                    if trailing_reasoning_delta is not None:
                        yield {
                            "type": "reasoning_delta",
                            "delta": trailing_reasoning_delta,
                        }
                    final_tool_calls_by_index = attempt_tool_calls_by_index
                except Exception as exc:
                    raise self._to_model_error(exc) from exc

        if not final_content:
            final_content = emitted_content
        if not final_reasoning:
            final_reasoning = emitted_reasoning
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": final_content,
                "tool_calls": _ordered_tool_calls(final_tool_calls_by_index),
                "usage": usage_totals,
                "reasoning": final_reasoning,
            },
        }
