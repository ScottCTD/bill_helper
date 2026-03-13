# CALLING SPEC:
# - Purpose: implement focused service logic for `pricing`.
# - Inputs: callers that import `backend/services/agent/pricing.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `pricing`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import litellm
from litellm.cost_calculator import cost_per_token

from backend.services.agent.error_policy import recoverable_result


MODEL_COST_MAP_SYNC_SECONDS = 60 * 60
_MODEL_COST_MAP_LOCK = threading.Lock()
_LAST_MODEL_COST_MAP_SYNC_AT: float | None = None
MODEL_COST_MAP_REFRESH_EXCEPTIONS = (Exception,)
COST_PER_TOKEN_EXCEPTIONS = (Exception,)


@dataclass(frozen=True)
class UsageCosts:
    input_cost_usd: float | None
    output_cost_usd: float | None
    total_cost_usd: float | None


def _cost_per_token(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_input_tokens: int | None = None,
    cache_creation_input_tokens: int | None = None,
) -> tuple[float, float]:
    cost_kwargs: dict[str, Any] = {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    if cache_read_input_tokens is not None:
        cost_kwargs["cache_read_input_tokens"] = cache_read_input_tokens
    if cache_creation_input_tokens is not None:
        cost_kwargs["cache_creation_input_tokens"] = cache_creation_input_tokens
    return cost_per_token(**cost_kwargs)


def _model_cost_candidates(model_name: str) -> list[str]:
    normalized = model_name.strip()
    if not normalized:
        return []
    return [normalized]


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _to_float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    # Keep values stable for JSON payloads and tests.
    return round(float(value), 12)


def _refresh_model_cost_map_if_due() -> None:
    global _LAST_MODEL_COST_MAP_SYNC_AT

    now = monotonic()
    last_sync = _LAST_MODEL_COST_MAP_SYNC_AT
    if last_sync is not None and (now - last_sync) < MODEL_COST_MAP_SYNC_SECONDS:
        return

    with _MODEL_COST_MAP_LOCK:
        now = monotonic()
        last_sync = _LAST_MODEL_COST_MAP_SYNC_AT
        if last_sync is not None and (now - last_sync) < MODEL_COST_MAP_SYNC_SECONDS:
            return
        try:
            litellm.model_cost = litellm.get_model_cost_map(litellm.model_cost_map_url)
        except MODEL_COST_MAP_REFRESH_EXCEPTIONS as exc:
            # LiteLLM already falls back to bundled pricing when remote fetch fails.
            recoverable_result(
                scope="pricing.refresh_model_cost_map",
                fallback=None,
                error=exc,
                context={"model_cost_map_url": str(litellm.model_cost_map_url)},
            )
        finally:
            _LAST_MODEL_COST_MAP_SYNC_AT = monotonic()


def calculate_usage_costs(
    *,
    model_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_read_tokens: int | None = None,
    cache_write_tokens: int | None = None,
) -> UsageCosts:
    if input_tokens is None and output_tokens is None:
        return UsageCosts(input_cost_usd=None, output_cost_usd=None, total_cost_usd=None)

    _refresh_model_cost_map_if_due()

    prompt_tokens = max(int(input_tokens or 0), 0)
    completion_tokens = max(int(output_tokens or 0), 0)
    cache_read_input_tokens = max(int(cache_read_tokens or 0), 0) if cache_read_tokens is not None else None
    cache_creation_input_tokens = max(int(cache_write_tokens or 0), 0) if cache_write_tokens is not None else None
    pricing_kwargs: dict[str, int] = {}
    if cache_read_input_tokens is not None:
        pricing_kwargs["cache_read_input_tokens"] = cache_read_input_tokens
    if cache_creation_input_tokens is not None:
        pricing_kwargs["cache_creation_input_tokens"] = cache_creation_input_tokens

    for candidate in _model_cost_candidates(model_name):
        try:
            prompt_cost_raw, completion_cost_raw = _cost_per_token(
                model=candidate,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                **pricing_kwargs,
            )
        except COST_PER_TOKEN_EXCEPTIONS as exc:
            recoverable_result(
                scope="pricing.cost_per_token",
                fallback=None,
                error=exc,
                context={
                    "model_name": candidate,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "cache_read_input_tokens": cache_read_input_tokens,
                    "cache_creation_input_tokens": cache_creation_input_tokens,
                },
            )
            continue

        prompt_cost = _to_decimal(prompt_cost_raw) if input_tokens is not None else None
        completion_cost = _to_decimal(completion_cost_raw) if output_tokens is not None else None
        if prompt_cost is None and completion_cost is None:
            continue

        total_cost: Decimal | None
        if prompt_cost is None and completion_cost is None:
            total_cost = None
        else:
            total_cost = (prompt_cost or Decimal("0")) + (completion_cost or Decimal("0"))

        return UsageCosts(
            input_cost_usd=_to_float(prompt_cost),
            output_cost_usd=_to_float(completion_cost),
            total_cost_usd=_to_float(total_cost),
        )

    return UsageCosts(input_cost_usd=None, output_cost_usd=None, total_cost_usd=None)
