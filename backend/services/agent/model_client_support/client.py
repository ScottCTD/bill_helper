# CALLING SPEC:
# - Purpose: implement focused service logic for `client`.
# - Inputs: callers that import `backend/services/agent/model_client_support/client.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `client`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from collections.abc import Iterator
import logging
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
from .environment import normalize_host, normalize_secret, supports_prompt_caching
from .streaming import (
    append_stream_content,
    finalize_stream_content,
    is_transient_ssl_bad_record_mac_error,
    merge_tool_call_delta,
    ordered_tool_calls,
)
from .usage import (
    apply_usage_totals,
    coerce_text,
    empty_usage_totals,
    normalize_usage,
    read_attr,
)

_PROMPT_CACHE_INJECTION_POINTS_MAX = 4
_UNSUPPORTED_TOOL_CHOICE_ERROR_SNIPPET = "no endpoints found that support the provided 'tool_choice' value"
logger = logging.getLogger(__name__)


class AgentModelError(RuntimeError):
    pass


def _message_text(exc: Exception) -> str:
    return str(getattr(exc, "message", None) or exc)


def _request_uses_forced_tool_choice(request: dict[str, Any]) -> bool:
    return "tool_choice" in request and request.get("tool_choice") != "auto"


def _is_unsupported_tool_choice_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code not in (400, 404, 422):
        return False
    return _UNSUPPORTED_TOOL_CHOICE_ERROR_SNIPPET in _message_text(exc).casefold()


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
        i = n - 1
        while i >= 0 and messages[i].get("role") == "tool":
            i -= 1
        if i >= 1 and messages[i].get("role") == "assistant":
            boundary = i - 1
            if boundary > 0:
                points.append({"location": "message", "index": boundary - n})
    elif last_role == "user":
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
        self._base_url = normalize_host(base_url)
        self._api_key = normalize_secret(api_key)

    def _base_request(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        response_format: Any = None,
    ) -> dict[str, Any]:
        effective_tools = self._tools if tools is None else tools
        request: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
        }
        if effective_tools:
            request["tools"] = effective_tools
            request["tool_choice"] = "auto" if tool_choice is None else tool_choice
        if response_format is not None:
            request["response_format"] = response_format
        if supports_prompt_caching(self._model_name):
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
            if not is_transient_ssl_bad_record_mac_error(exc):
                raise
            logger.warning(
                "retrying model completion after transient SSL transport error",
                extra={
                    "model_name": self._model_name,
                    "error_type": type(exc).__name__,
                },
            )
            return litellm.completion(**request)

    def _completion_with_request_fallbacks(self, request: dict[str, Any]) -> Any:
        try:
            return self._completion_with_transient_ssl_retry(request)
        except Exception as exc:
            if not _request_uses_forced_tool_choice(request) or not _is_unsupported_tool_choice_error(
                exc
            ):
                raise
            logger.info(
                "retrying model completion without forced tool_choice after provider rejection",
                extra={"model_name": self._model_name},
            )
            retry_request = {
                key: value for key, value in request.items() if key != "tool_choice"
            }
            return self._completion_with_transient_ssl_retry(retry_request)

    def _chat_completion_once(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        response_format: Any = None,
    ) -> Any:
        request = self._base_request(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
        )
        try:
            return self._completion_with_request_fallbacks(request)
        except Exception as exc:
            raise self._to_model_error(exc) from exc

    def _stream_completion_once(self, request: dict[str, Any]) -> Any:
        try:
            return self._completion_with_request_fallbacks(request)
        except OpenAIError as exc:
            status_code = getattr(exc, "status_code", None)
            if request.get("stream_options") and status_code in (400, 422):
                retry_request = {
                    key: value
                    for key, value in request.items()
                    if key != "stream_options"
                }
                return self._completion_with_request_fallbacks(retry_request)
            raise

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        response_format: Any = None,
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
                response = self._chat_completion_once(
                    messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    response_format=response_format,
                )
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
            "usage": normalize_usage(getattr(response, "usage", None)),
        }

    def complete_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: Any = None,
        response_format: Any = None,
    ) -> Iterator[dict[str, Any]]:
        request = self._base_request(
            messages,
            tools=tools,
            tool_choice=tool_choice,
            response_format=response_format,
        )
        request["stream"] = True
        request["stream_options"] = {"include_usage": True}

        emitted_content = ""
        final_content = ""
        emitted_reasoning = ""
        final_reasoning = ""
        usage_totals = empty_usage_totals()
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
                        apply_usage_totals(
                            usage_totals,
                            normalize_usage(read_attr(chunk, "usage")),
                        )

                        choices = read_attr(chunk, "choices") or []
                        for choice in choices:
                            delta = read_attr(choice, "delta")
                            if delta is None:
                                continue

                            reasoning_delta = coerce_text(
                                read_attr(delta, "reasoning_content")
                            ) or coerce_text(read_attr(delta, "reasoning"))
                            if reasoning_delta is not None:
                                emitted_reasoning, attempt_reasoning, streamed_reasoning_delta = (
                                    append_stream_content(
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

                            content_delta = coerce_text(read_attr(delta, "content"))
                            if content_delta is not None:
                                emitted_content, attempt_content, text_delta = (
                                    append_stream_content(
                                        emitted_content=emitted_content,
                                        attempt_content=attempt_content,
                                        content_delta=content_delta,
                                    )
                                )
                                if text_delta is not None:
                                    yield {"type": "text_delta", "delta": text_delta}

                            for tool_call_delta in read_attr(delta, "tool_calls") or []:
                                merge_tool_call_delta(
                                    tool_calls_by_index=attempt_tool_calls_by_index,
                                    tool_call_delta=tool_call_delta,
                                )

                    emitted_content, final_content, trailing_delta = finalize_stream_content(
                        emitted_content=emitted_content,
                        attempt_content=attempt_content,
                    )
                    if trailing_delta is not None:
                        yield {"type": "text_delta", "delta": trailing_delta}
                    emitted_reasoning, final_reasoning, trailing_reasoning_delta = finalize_stream_content(
                        emitted_content=emitted_reasoning,
                        attempt_content=attempt_reasoning,
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
                "tool_calls": ordered_tool_calls(final_tool_calls_by_index),
                "usage": usage_totals,
                "reasoning": final_reasoning,
            },
        }
