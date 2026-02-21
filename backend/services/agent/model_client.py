from __future__ import annotations

from collections.abc import Iterator
from threading import Lock
from typing import Any

import litellm
from litellm import APIConnectionError, APIError, OpenAIError, Timeout
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class AgentModelError(RuntimeError):
    pass


_LANGFUSE_CALLBACK_NAME = "langfuse"
_LANGFUSE_CALLBACK_LOCK = Lock()
_TRANSIENT_SSL_BAD_RECORD_MAC_MARKERS = (
    "sslv3_alert_bad_record_mac",
    "sslv3 alert bad record mac",
    "bad record mac",
)
_PROMPT_CACHE_INJECTION_POINTS_MAX = 4


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


def _normalize_observability_text(value: Any, *, max_length: int = 128) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:max_length]


def _normalize_callback_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str):
                normalized.append(item)
        return normalized
    return []


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
    except Exception:
        return False


def _cache_injection_points_for_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Prefer stable anchors for tool-heavy loops:
    # 1) all system messages (long-lived instruction/context prefix)
    # 2) latest user turn (stable across intra-run tool steps)
    if len(messages) < 2:
        return []

    points: list[dict[str, Any]] = [
        {"location": "message", "role": "system"},
    ]

    latest_user_index = next(
        (index for index in range(len(messages) - 1, -1, -1) if messages[index].get("role") == "user"),
        None,
    )
    if latest_user_index is not None:
        negative_index = latest_user_index - len(messages)
        points.append({"location": "message", "index": negative_index})

    unique_points: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, Any], ...]] = set()
    for point in points:
        key = tuple(sorted(point.items()))
        if key in seen:
            continue
        seen.add(key)
        unique_points.append(point)
    return unique_points[:_PROMPT_CACHE_INJECTION_POINTS_MAX]


def _enable_langfuse_callbacks() -> None:
    with _LANGFUSE_CALLBACK_LOCK:
        for attribute_name in ("success_callback", "failure_callback"):
            callbacks = _normalize_callback_values(getattr(litellm, attribute_name, None))
            if _LANGFUSE_CALLBACK_NAME not in callbacks:
                callbacks.append(_LANGFUSE_CALLBACK_NAME)
                setattr(litellm, attribute_name, callbacks)


def _build_observability_extra_body(observability: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(observability, dict):
        return None

    payload: dict[str, Any] = {}
    user = _normalize_observability_text(observability.get("user"))
    session_id = _normalize_observability_text(observability.get("session_id"))
    trace = observability.get("trace")

    if user is not None:
        payload["user"] = user
    if session_id is not None:
        payload["session_id"] = session_id
    if isinstance(trace, dict) and trace:
        payload["trace"] = trace

    return payload or None


def _coerce_step(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _build_observability_metadata(observability: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(observability, dict):
        return None

    metadata: dict[str, Any] = {}
    trace_metadata: dict[str, Any] = {}

    user = _normalize_observability_text(observability.get("user"), max_length=256)
    session_id = _normalize_observability_text(observability.get("session_id"), max_length=256)
    trace = observability.get("trace")

    if user is not None:
        metadata["trace_user_id"] = user
    if session_id is not None:
        metadata["session_id"] = session_id

    generation_name = "agent_turn"
    if isinstance(trace, dict):
        trace_id = _normalize_observability_text(trace.get("trace_id"), max_length=256)
        trace_name = _normalize_observability_text(trace.get("trace_name"), max_length=256)
        generation_name = _normalize_observability_text(trace.get("generation_name"), max_length=128)
        thread_id = _normalize_observability_text(trace.get("thread_id"), max_length=256)
        run_id = _normalize_observability_text(trace.get("run_id"), max_length=256)
        step = _coerce_step(trace.get("step"))
        is_first_run_in_thread = trace.get("is_first_run_in_thread", True)
        run_index = _coerce_step(trace.get("run_index"))

        if generation_name is None and run_index is not None and step is not None:
            generation_name = f"agent_turn_run_{run_index}_step_{step}"
        elif generation_name is None and step is not None:
            generation_name = f"agent_turn_step_{step}"
        elif generation_name is None:
            generation_name = "agent_turn"

        use_existing_trace = (step is not None and step > 1) or (
            isinstance(is_first_run_in_thread, bool) and not is_first_run_in_thread
        )
        if trace_id is not None:
            if use_existing_trace:
                metadata["existing_trace_id"] = trace_id
            else:
                metadata["trace_id"] = trace_id
        if trace_name is not None:
            metadata["trace_name"] = trace_name
        if thread_id is not None:
            trace_metadata["thread_id"] = thread_id
        if run_id is not None:
            trace_metadata["run_id"] = run_id

    metadata["generation_name"] = generation_name
    if trace_metadata:
        metadata["trace_metadata"] = trace_metadata

    return metadata or None


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


def validate_litellm_environment(*, model_name: str) -> tuple[bool, list[str], str]:
    normalized_model = (model_name or "").strip() or "google/gemini-3-flash-preview"
    try:
        validation = litellm.validate_environment(
            model=normalized_model,
        )
    except Exception:
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
        langfuse_public_key: str | None = None,
        langfuse_secret_key: str | None = None,
        langfuse_host: str | None = None,
    ) -> None:
        self._model_name = (model_name or "").strip() or "google/gemini-3-flash-preview"
        self._tools = tools
        self._retry_max_attempts = max(1, retry_max_attempts)
        self._retry_initial_wait_seconds = max(0.0, retry_initial_wait_seconds)
        self._retry_max_wait_seconds = max(0.0, retry_max_wait_seconds)
        self._retry_backoff_multiplier = max(1.0, retry_backoff_multiplier)
        self._langfuse_public_key = _normalize_secret(langfuse_public_key)
        self._langfuse_secret_key = _normalize_secret(langfuse_secret_key)
        self._langfuse_host = _normalize_host(langfuse_host)
        self._langfuse_enabled = self._langfuse_public_key is not None and self._langfuse_secret_key is not None
        if self._langfuse_enabled:
            _enable_langfuse_callbacks()

    def _base_request(
        self,
        messages: list[dict[str, Any]],
        *,
        observability: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "tools": self._tools,
            "tool_choice": "auto",
            "temperature": 0.1,
        }
        if _supports_prompt_caching(self._model_name):
            injection_points = _cache_injection_points_for_messages(messages)
            if injection_points:
                request["cache_control_injection_points"] = injection_points

        if self._langfuse_enabled:
            request["langfuse_public_key"] = self._langfuse_public_key
            request["langfuse_secret_key"] = self._langfuse_secret_key
            if self._langfuse_host is not None:
                request["langfuse_host"] = self._langfuse_host

        metadata = _build_observability_metadata(observability)
        if metadata is not None:
            request["metadata"] = metadata

        extra_body = _build_observability_extra_body(observability)
        if extra_body is not None:
            request["extra_body"] = extra_body
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
        *,
        observability: dict[str, Any] | None = None,
    ) -> Any:
        request = self._base_request(messages, observability=observability)
        try:
            return self._completion_with_transient_ssl_retry(request)
        except Exception as exc:
            raise self._to_model_error(exc) from exc

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        observability: dict[str, Any] | None = None,
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
                response = self._chat_completion_once(messages, observability=observability)
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
        *,
        observability: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        request = self._base_request(messages, observability=observability)
        request["stream"] = True
        request["stream_options"] = {"include_usage": True}

        emitted_content = ""
        final_content = ""
        usage_totals: dict[str, int | None] = {
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }
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
                    attempt_content = ""
                    attempt_tool_calls_by_index: dict[int, dict[str, Any]] = {}
                    try:
                        stream = self._completion_with_transient_ssl_retry(request)
                    except OpenAIError as exc:
                        status_code = getattr(exc, "status_code", None)
                        if request.get("stream_options") and status_code in (400, 422):
                            # Some OpenAI-compatible providers reject `stream_options`; retry once without it.
                            retry_request = dict(request)
                            retry_request.pop("stream_options", None)
                            stream = self._completion_with_transient_ssl_retry(retry_request)
                        else:
                            raise

                    for chunk in stream:
                        usage = _normalize_usage(_read_attr(chunk, "usage"))
                        for field, value in usage.items():
                            if value is not None:
                                usage_totals[field] = value

                        choices = _read_attr(chunk, "choices") or []
                        for choice in choices:
                            delta = _read_attr(choice, "delta")
                            if delta is None:
                                continue

                            content_delta = _coerce_text(_read_attr(delta, "content"))
                            if content_delta is not None:
                                attempt_content = f"{attempt_content}{content_delta}"
                                if attempt_content.startswith(emitted_content):
                                    suffix = attempt_content[len(emitted_content) :]
                                    if suffix:
                                        emitted_content = attempt_content
                                        yield {"type": "text_delta", "delta": suffix}
                                elif emitted_content.startswith(attempt_content):
                                    # Retry replaying an already-emitted prefix; suppress duplicates.
                                    continue
                                else:
                                    raise AgentModelError("model request failed: stream retry produced divergent output")

                            for tool_call_delta in _read_attr(delta, "tool_calls") or []:
                                index = _coerce_index(_read_attr(tool_call_delta, "index"))
                                if index is None:
                                    continue
                                current = attempt_tool_calls_by_index.setdefault(
                                    index,
                                    {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    },
                                )

                                delta_id = _coerce_text(_read_attr(tool_call_delta, "id"))
                                if delta_id is not None:
                                    if not current["id"]:
                                        current["id"] = delta_id

                                delta_type = _coerce_text(_read_attr(tool_call_delta, "type"))
                                if delta_type is not None:
                                    current["type"] = delta_type

                                delta_function = _read_attr(tool_call_delta, "function")
                                delta_name = _coerce_text(_read_attr(delta_function, "name"))
                                if delta_name is not None:
                                    current["function"]["name"] = f"{current['function']['name']}{delta_name}"

                                delta_arguments = _coerce_text(_read_attr(delta_function, "arguments"))
                                if delta_arguments is not None:
                                    current["function"]["arguments"] = f"{current['function']['arguments']}{delta_arguments}"

                    if not attempt_content and emitted_content:
                        final_content = emitted_content
                    else:
                        if attempt_content.startswith(emitted_content):
                            suffix = attempt_content[len(emitted_content) :]
                            if suffix:
                                emitted_content = attempt_content
                                yield {"type": "text_delta", "delta": suffix}
                            final_content = attempt_content
                        else:
                            final_content = emitted_content
                    final_tool_calls_by_index = attempt_tool_calls_by_index
                except Exception as exc:
                    raise self._to_model_error(exc) from exc

        if not final_content:
            final_content = emitted_content
        tool_calls = [final_tool_calls_by_index[index] for index in sorted(final_tool_calls_by_index)]
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": final_content,
                "tool_calls": tool_calls,
                "usage": usage_totals,
            },
        }
