# Agent Surface Follow-Up

## Status

Deferred. Record the cleanup plan, but do not refactor the current implementation in this work item.

## Finding

The current `surface` support is acceptable for the existing `app` and `telegram` transports, but the concern leaks through multiple layers:

- router request parsing
- run creation and execution orchestration
- prompt assembly
- terminal reply serialization

This is manageable for two surfaces, but it will get brittle if more transports or more surface-specific behavior are added.

## Current Behavior To Preserve

- `AgentRun.surface` persists the run origin so replay and debugging can distinguish app-originated and Telegram-originated runs.
- prompt rendering can request plain-text-friendly responses for Telegram runs
- terminal reply serialization can flatten rich markdown for Telegram consumers
- explicit `model_name` selection continues to work independently of `surface`

## Root Cause

`surface` is currently passed as a raw string across several service seams instead of being represented as a narrow policy abstraction. This couples transport concerns to execution plumbing.

Affected modules today:

- `backend/routers/agent.py`
- `backend/services/agent/execution.py`
- `backend/services/agent/runtime.py`
- `backend/services/agent/message_history.py`
- `backend/services/agent/serializers.py`
- `backend/services/agent/prompts.py`

## Desired End State

- persist run origin as `origin_surface` or equivalent durable metadata on the run
- keep router ownership limited to HTTP translation
- move surface-specific prompt and output behavior behind a focused policy or registry
- stop threading raw surface strings through unrelated orchestration code when that code does not need transport knowledge
- keep the transport-specific formatting rules centralized in one canonical place

## Proposed Refactor Shape

1. Introduce a small surface policy module keyed by surface name.
2. Let run creation resolve the policy once, then persist only the durable run metadata needed for replay.
3. Move prompt directives and terminal reply formatting behind the policy.
4. Keep execution/runtime APIs focused on domain inputs such as selected model, thread, and message, with surface-specific behavior accessed through the policy instead of extra string parameters where possible.
5. Rename fields only if the new names materially improve clarity; avoid compatibility shims unless they are still required.

## Non-Goals

- no behavior change for the current app or Telegram transport
- no broader agent runtime redesign
- no transport unification beyond the surface-specific prompt/output seams

## Verification Expectations For The Future Refactor

- `uv run python -m py_compile ...` on touched Python modules
- `OPENROUTER_API_KEY=test uv run pytest backend/tests telegram/tests -q`
- `uv run python scripts/check_docs_sync.py`

## Exit Criteria

- the active transport behavior is unchanged
- prompt/output behavior remains correct for Telegram
- the number of cross-layer `surface` parameters is reduced
- the resulting ownership boundaries align with router/service standards in `AGENTS.md`
