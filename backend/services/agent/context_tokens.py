from __future__ import annotations

from copy import deepcopy
from typing import Any

import litellm


def count_context_tokens(
    *,
    model_name: str,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> int | None:
    try:
        count = litellm.token_counter(
            model=model_name,
            messages=deepcopy(messages),
            tools=deepcopy(tools) if tools is not None else None,
            use_default_image_token_count=True,
        )
    except Exception:
        return None

    if not isinstance(count, int):
        try:
            return int(count)
        except (TypeError, ValueError):
            return None
    return count
