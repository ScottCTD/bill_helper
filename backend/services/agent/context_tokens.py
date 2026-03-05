from __future__ import annotations

from copy import deepcopy
from typing import Any

import litellm

from backend.services.agent.error_policy import RecoverableResult, recoverable_result


TOKEN_COUNTER_EXCEPTIONS = (
    AttributeError,
    KeyError,
    RuntimeError,
    TypeError,
    ValueError,
)


def count_context_tokens_result(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> RecoverableResult[int | None]:
    try:
        count = litellm.token_counter(
            model=model_name,
            messages=deepcopy(messages),
            tools=deepcopy(tools) if tools is not None else None,
            use_default_image_token_count=True,
        )
    except TOKEN_COUNTER_EXCEPTIONS as exc:
        return recoverable_result(
            scope="context_tokens.token_counter",
            fallback=None,
            error=exc,
            context={"model_name": model_name},
        )

    if isinstance(count, int):
        return RecoverableResult(value=count)

    try:
        coerced = int(count)
    except (TypeError, ValueError) as exc:
        return recoverable_result(
            scope="context_tokens.token_counter_coerce",
            fallback=None,
            error=exc,
            context={"model_name": model_name, "raw_type": type(count).__name__},
        )
    return RecoverableResult(value=coerced)


def count_context_tokens(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> int | None:
    return count_context_tokens_result(
        model_name=model_name,
        messages=messages,
        tools=tools,
    ).value
