# Agent Cache-Token Pricing TODO

## Summary

The agent run cost shown in the UI is mispriced for cache-enabled models.

Current behavior:

- usage normalization persists `input_tokens`, `output_tokens`, `cache_read_tokens`, and `cache_write_tokens`
- pricing only uses `input_tokens` and `output_tokens`
- the frontend sums backend-provided `total_cost_usd`

That means cached prompt reads are billed as full-price prompt tokens, and cache writes are billed as normal prompt tokens instead of their cache-write rate.

For long Bedrock Anthropic threads, the net effect is usually an inflated displayed total because cache reads tend to dominate.

## Evidence

### Current code path

- [`backend/services/agent/model_client.py`](backend/services/agent/model_client.py) normalizes provider usage and extracts both `cache_read_tokens` and `cache_write_tokens`
- [`backend/services/agent/serializers.py`](backend/services/agent/serializers.py) calls `calculate_usage_costs()` with only `input_tokens` and `output_tokens`
- [`backend/services/agent/pricing.py`](backend/services/agent/pricing.py) forwards only `prompt_tokens` and `completion_tokens` into LiteLLM `cost_per_token()`
- [`frontend/src/features/agent/activity.ts`](frontend/src/features/agent/activity.ts) builds thread totals by summing backend `total_cost_usd`

### Local LiteLLM confirmation

The installed LiteLLM version already supports cache-aware pricing inputs:

```python
cost_per_token(
    model=...,
    prompt_tokens=...,
    completion_tokens=...,
    cache_creation_input_tokens=...,
    cache_read_input_tokens=...,
)
```

The local model-cost entry for `us.anthropic.claude-sonnet-4-6` includes separate rates for:

- `input_cost_per_token = 3.3e-06`
- `cache_read_input_token_cost = 3.3e-07`
- `cache_creation_input_token_cost = 4.125e-06`

### Reproduction example

Observed usage shape:

- `input_tokens = 120`
- `output_tokens = 15`
- `cache_read_tokens = 80`
- `cache_write_tokens = 20`

Current app pricing path:

- prompt cost = `0.000396`
- output cost = `0.0002475`
- total cost = `0.0006435`

Cache-aware LiteLLM pricing:

- prompt cost = `0.0001749`
- output cost = `0.0002475`
- total cost = `0.0004224`

In this example, the currently displayed total is overstated by `0.0002211` USD, about `34.4%`.

## Root Cause

The app already captures the token categories needed for correct pricing, but the pricing seam drops the cache-specific fields before calling LiteLLM.

No database migration is required for the baseline fix because `cache_read_tokens` and `cache_write_tokens` are already persisted and serialized.

## TODO

- Update [`backend/services/agent/pricing.py`](backend/services/agent/pricing.py) so `calculate_usage_costs()` accepts `cache_read_tokens` and `cache_write_tokens`.
- Pass `cache_read_input_tokens` and `cache_creation_input_tokens` into LiteLLM `cost_per_token()`.
- Update [`backend/services/agent/serializers.py`](backend/services/agent/serializers.py) to forward `run.cache_read_tokens` and `run.cache_write_tokens`.
- Add pricing tests that cover:
  - cache-read discount is applied
  - cache-write premium is applied
  - mixed cached and uncached prompt tokens
  - missing cache fields still fall back cleanly
- Decide API semantics for `input_cost_usd`:
  - compatibility option: keep it as the full prompt-side cost after cache-aware pricing
  - richer option: add separate cache-read/cache-write cost fields later if the UI needs a breakdown
- After the code change lands, update stable docs that currently describe pricing as `input_tokens + output_tokens` only.

## Verification Plan

- `uv run --extra dev python -m py_compile backend/services/agent/pricing.py backend/services/agent/serializers.py`
- `uv run --extra dev pytest backend/tests/test_agent_pricing.py backend/tests/test_agent.py -q`
- `uv run python scripts/check_docs_sync.py`

## Notes

- The user report about cache reads is directionally correct.
- The bug is slightly broader than cache reads alone because cache writes are also mispriced today.
- The frontend total-cost display should correct itself once backend `total_cost_usd` is fixed; no UI change is required for baseline correctness.
