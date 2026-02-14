from __future__ import annotations

from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class AgentModelError(RuntimeError):
    pass


def _normalize_observability_text(value: Any, *, max_length: int = 128) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:max_length]


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
        cache_read_tokens = _read_int(prompt_details, "cache_read_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(prompt_details, "cache_read_input_tokens")
    if cache_read_tokens is None:
        cache_read_tokens = _read_int(prompt_details, "cached_tokens")

    cache_write_tokens = _read_int(usage, "cache_write_tokens")
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


class OpenRouterModelClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str,
        tools: list[dict[str, Any]],
        retry_max_attempts: int,
        retry_initial_wait_seconds: float,
        retry_max_wait_seconds: float,
        retry_backoff_multiplier: float,
    ) -> None:
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
        )
        self._model_name = model_name
        self._tools = tools
        self._retry_max_attempts = max(1, retry_max_attempts)
        self._retry_initial_wait_seconds = max(0.0, retry_initial_wait_seconds)
        self._retry_max_wait_seconds = max(0.0, retry_max_wait_seconds)
        self._retry_backoff_multiplier = max(1.0, retry_backoff_multiplier)

    def _chat_completion_once(
        self,
        messages: list[dict[str, Any]],
        *,
        observability: dict[str, Any] | None = None,
    ) -> Any:
        request: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "tools": self._tools,
            "tool_choice": "auto",
            "temperature": 0.1,
        }
        extra_body = _build_observability_extra_body(observability)
        if extra_body is not None:
            request["extra_body"] = extra_body
        try:
            return self._client.chat.completions.create(**request)
        except APIStatusError as exc:
            detail = exc.body if exc.body is not None else str(exc)
            raise AgentModelError(f"model request failed ({exc.status_code}): {detail}") from exc
        except APITimeoutError as exc:
            raise AgentModelError("model request timed out") from exc
        except APIConnectionError as exc:
            raise AgentModelError(f"model request failed: {str(exc)}") from exc
        except OpenAIError as exc:
            raise AgentModelError(f"model request failed: {str(exc)}") from exc

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
