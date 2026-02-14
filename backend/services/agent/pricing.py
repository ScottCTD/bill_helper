from __future__ import annotations

import threading
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from time import monotonic
from typing import Any

import litellm
from litellm.cost_calculator import cost_per_token


MODEL_COST_MAP_SYNC_SECONDS = 60 * 60
_MODEL_COST_MAP_LOCK = threading.Lock()
_LAST_MODEL_COST_MAP_SYNC_AT: float | None = None


@dataclass(frozen=True)
class UsageCosts:
    input_cost_usd: float | None
    output_cost_usd: float | None
    total_cost_usd: float | None


def _cost_per_token(*, model: str, prompt_tokens: int, completion_tokens: int) -> tuple[float, float]:
    return cost_per_token(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


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
        except Exception:
            # LiteLLM already falls back to bundled pricing when remote fetch fails.
            pass
        finally:
            _LAST_MODEL_COST_MAP_SYNC_AT = monotonic()


def calculate_usage_costs(
    *,
    model_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> UsageCosts:
    if input_tokens is None and output_tokens is None:
        return UsageCosts(input_cost_usd=None, output_cost_usd=None, total_cost_usd=None)

    _refresh_model_cost_map_if_due()

    prompt_tokens = max(int(input_tokens or 0), 0)
    completion_tokens = max(int(output_tokens or 0), 0)

    for candidate in _model_cost_candidates(model_name):
        try:
            prompt_cost_raw, completion_cost_raw = _cost_per_token(
                model=candidate,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        except Exception:
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
