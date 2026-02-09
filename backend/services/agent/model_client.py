from __future__ import annotations

from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, OpenAIError


class AgentModelError(RuntimeError):
    pass


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
    ) -> None:
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
        )
        self._model_name = model_name
        self._tools = tools

    def complete(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = self._client.chat.completions.create(
                model=self._model_name,
                messages=messages,
                tools=self._tools,
                tool_choice="auto",
                temperature=0.1,
            )
        except APIStatusError as exc:
            detail = exc.body if exc.body is not None else str(exc)
            raise AgentModelError(f"model request failed ({exc.status_code}): {detail}") from exc
        except APITimeoutError as exc:
            raise AgentModelError("model request timed out") from exc
        except APIConnectionError as exc:
            raise AgentModelError(f"model request failed: {str(exc)}") from exc
        except OpenAIError as exc:
            raise AgentModelError(f"model request failed: {str(exc)}") from exc

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
