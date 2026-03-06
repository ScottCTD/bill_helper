# Backend Guide

This module hosts the FastAPI app, SQLAlchemy models, Pydantic schemas, and domain services.

## Fast Entry Points

- App startup: `backend/main.py`
- Module launcher: `backend/__main__.py` (`python -m backend`)
- API routers: `backend/routers/*`
- DB metadata/runtime bootstrap: `backend/db_meta.py`, `backend/database.py`
- Domain logic: `backend/services/*`
- Persistence model compatibility facade: `backend/models.py` (domain modules: `backend/models_finance.py`, `backend/models_agent.py`)
- API contract compatibility facade: `backend/schemas.py` (domain modules: `backend/schemas_finance.py`, `backend/schemas_agent.py`)
- Enum compatibility facade: `backend/enums.py` (domain modules: `backend/enums_finance.py`, `backend/enums_agent.py`)
- Tests: `backend/tests/*`

Initialization contract:

- `backend.main` exposes `create_app()` as the explicit app factory.
- Uvicorn runs with factory mode (`backend.main:create_app`) so app setup does not execute at module import time.
- Agent background run threads receive an injected session factory (`get_session_maker`) instead of opening sessions through implicit module-global state.

## File Map

- `backend/routers/entries.py`: entry CRUD, filters, link creation.
- `backend/routers/groups.py`: derived group summaries and graph detail read models.
- `backend/routers/dashboard.py`: monthly dashboard analytics endpoint.
- `backend/routers/agent.py`: agent thread/run/review endpoints.
- `backend/routers/settings.py`: runtime settings read/update endpoints.
- `backend/services/finance.py`: reconciliation + dashboard aggregations/projection.
- `backend/services/crud_policy.py`: shared router-side domain policy primitives (required-name normalization, uniqueness/conflict guards, and standardized policy-violation translation).
- `backend/services/agent/change_contracts.py`: shared proposal/apply payload contract validation + normalization.
- `backend/services/agent/change_apply.py`: apply approved proposals.
- `backend/services/agent/attachments.py`: attachment lifecycle helpers (store upload bytes, derive per-thread attachment directories, and cleanup on thread delete).
- `backend/services/agent/execution.py`: agent execution policy service (message validation, attachment persistence handoff, run start/background continuation, current-context token calculation) plus stable benchmark/test execution facade methods.
- `backend/services/agent/attachment_content.py` + `backend/services/agent/user_context.py`: content-building helpers split by concern (attachment parsing/vision payloads vs account/user context assembly).
- `backend/services/agent/runtime_state.py`: runtime event/tool-call persistence state helpers extracted from `runtime.py`.
- `backend/services/agent/benchmark_interface.py`: stable benchmark-facing case execution contract that returns normalized predictions + trace metadata without exposing runner to runtime internals.
- `backend/services/agent/run_orchestrator.py`: shared run-step state machine for sync runtime, streaming runtime, and benchmark execution adapters.
- `backend/services/agent/protocol_helpers.py`: shared helper contracts for tool-call decoding and normalized usage extraction/accumulation across runtime and benchmark.
- `backend/services/agent/protocol.py`: compatibility facade that re-exports protocol helper APIs.
- `backend/services/agent/error_policy.py`: shared recoverable-error policy utilities (`RecoverableResult` + contextual fallback logging) for agent modules.
- `backend/services/agent/tool_args.py`: tool argument schemas and normalization helpers.
- `backend/services/agent/tool_handlers_read.py`: read-only and intermediate-update tool handlers.
- `backend/services/agent/tool_handlers_propose.py`: proposal/update/remove handlers for review-gated mutations.
- `backend/services/agent/proposal_patching.py`: pending-proposal patch-map application helpers.
- `backend/services/agent/tool_runtime.py`: tool registry + runtime execution/retry policy.
- `backend/services/agent/tools.py`: thin composition facade for tool runtime exports.
- `backend/services/runtime_settings.py`: persisted override + env fallback resolver for runtime settings, plus DB-backed `user_memory`.
- `backend/services/runtime_settings_normalization.py`: shared normalization/validation helpers used by runtime settings schemas and resolver.
- `backend/services/accounts.py`: account create/update ownership + entity-resolution command workflows.
- `backend/services/serializers.py`: ORM -> API schema conversion.
- `backend/db_meta.py`: side-effect-free SQLAlchemy metadata root (`Base`).
- `backend/database.py`: explicit engine/session factories + cached runtime accessors (`get_engine`, `get_session_maker`, `get_db`).
- `backend/models_finance.py` / `backend/models_agent.py`: split ledger vs agent ORM contract modules.
- `backend/schemas_finance.py` / `backend/schemas_agent.py`: split ledger/settings vs agent API schema modules.
- `backend/tests/test_import_conventions.py`: enforces explicit domain-module imports (`*_finance` / `*_agent`) and blocks new imports from compatibility facades.

## Common Change Paths

## 1) Entry Contract Changes

Touch together:

- `backend/models.py`
- `backend/models_finance.py`
- `backend/schemas.py`
- `backend/schemas_finance.py`
- `backend/routers/entries.py`
- `backend/services/serializers.py`
- `backend/tests/test_entries.py`
- Alembic migration in `alembic/versions`

## 2) Dashboard Analytics Changes

Touch together:

- `backend/services/finance.py`
- `backend/routers/dashboard.py`
- `backend/schemas.py` (`DashboardRead` and nested types)
- `backend/tests/test_finance.py`

Current behavior:

- dashboard aggregation ignores internal account-to-account transfers when both sides resolve through account-category entities (including linked `Account.entity_id` values), so monthly in/out cards and chart rollups represent external cash flow only

## 3) Entry Group Graph Read Model Changes

Touch together:

- `backend/routers/groups.py`
- `backend/services/groups.py`
- `backend/schemas.py`
- `backend/tests/test_entries.py`

## 4) Agent Review Apply Changes

Touch together:

- `backend/services/agent/change_contracts.py`
- `backend/services/agent/change_apply.py`
- `backend/services/agent/review.py`
- `backend/services/agent/tools.py` (proposal/read outputs)
- `backend/tests/test_agent.py`

## 5) Agent Run Lifecycle / Interrupt Changes

Touch together:

- `backend/routers/agent.py`
- `backend/services/agent/attachments.py`
- `backend/services/agent/execution.py`
- `backend/services/agent/context_tokens.py`
- `backend/services/agent/runtime.py`
- `backend/services/agent/run_orchestrator.py`
- `benchmark/runner.py` (if benchmark parity behavior changes)
- `backend/tests/test_agent.py`

## 6) Runtime Settings Changes

Touch together:

- `backend/routers/settings.py`
- `backend/services/runtime_settings.py`
- runtime consumers (`backend/routers/*`, `backend/services/agent/*`) that depend on resolved settings
- `backend/schemas.py`
- `backend/schemas_finance.py`
- `backend/tests/test_settings.py`
- Alembic migration in `alembic/versions`

## Run and Verify

```bash
uv run alembic upgrade head
uv run --extra dev pytest
uv run python scripts/check_docs_sync.py
```

## Current Constraints

- Account contracts include `name`, `markdown_body`, `currency_code`, and owner/active state; legacy `institution`/`account_type` fields were removed.
- Agent current-user system context now includes per-account `notes_markdown` summaries, with truncation safeguards for oversized markdown/data-url image payloads.
- Runtime settings include optional `user_memory` text that is injected into every agent system prompt.
- `/api/v1/settings` reports `current_user_name` from request principal; identity is not mutable via runtime settings overrides.
- Agent system prompt current-date context is rendered in `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` (default `America/Toronto`).
- Entry-level `status` was removed; agent review state remains only on `agent_change_items`.
- Entry groups are derived from entry-link connected components; `/groups` is read-model only (no group create/update/delete endpoints).
- `GET /api/v1/groups` omits singleton components (`entry_count < 2`) to focus on linked groups.
- `GET /api/v1/groups*` and `GET /api/v1/dashboard` are principal-scoped by owned-resource visibility.
- `POST`/`PATCH` mutations on `entities`, `tags`, and taxonomy terms require admin principal.
- Agent tool contracts are name/selector-based (no domain IDs in model-facing arguments/outputs).
- Entry selector/patch tool args are resilient to accidental nested JSON-object string encoding and normalize to objects before validation.
- Proposal and apply paths share a single payload contract layer in `backend/services/agent/change_contracts.py`; patch-map editable-root validation for `update_pending_proposal` also lives there.
- Service helper naming now encodes mutation intent: `ensure_*` helpers may create/write+flush, while `read_*`/`find_*` helpers are side-effect free.
- Agent service imports now use explicit module paths (`backend.services.agent.runtime` / `backend.services.agent.review`) instead of package-level re-export barrels; `backend/tests/test_import_conventions.py` enforces this in CI.
- Database bootstrap now avoids import-time engine/session initialization; migrations/scripts/tests construct explicit engine/session handles via `build_engine` + `build_session_maker`.
- Agent emits progress notes via `send_intermediate_update`; when a run needs tool calls, prompt policy requires it as the first tool call, and runtime persists them as `agent_run_events.reasoning_update` instead of fake tool-call rows.
- Entry create proposals can omit currency and fall back to the resolved runtime default currency (`/settings` override, else `BILL_HELPER_DEFAULT_CURRENCY_CODE`).
- Proposal tool outputs include `proposal_id` + `proposal_short_id` for follow-up reference in later turns.
- Pending proposals can be edited or removed in-thread via `update_pending_proposal` / `remove_pending_proposal` (pending-only, thread-scoped).
- Tag deletion proposals are blocked when the tag is still referenced by any non-deleted entries; apply path re-validates this constraint before delete.
- Entry proposals can reference entities that already exist or that are already pending as `create_entity` proposals in the same thread.
  Approving those entry/update proposals is blocked until the entity dependency is resolved. If the related entity proposal is rejected or removed, the dependent entry proposals remain pending and must be updated before they can be approved.
- Agent prompt policy requires duplicate-entry checks to prefer `propose_update_entry` when new input complements an existing entry.
- Agent prompt policy requires canonical/generalized tag and entity naming.
  Tags must stay general (for example, `groceries`, `dining`, `online`) instead of colliding with entities/merchants (for example, `credit`, `loblaw`, `heytea`), and tags should omit locations unless the user explicitly requests location-specific tagging.
  Entity abbreviations/store-branch variants still normalize to base names.
- Agent prompt policy now separates ordering rules from explicit new-record specifications for entries, tags, and entities.
  New entry specs require grounding all fields in explicit source facts and avoiding invented missing details.
- Agent prompt/tool policy requires human-readable `markdown_notes` formatting that preserves input detail; short notes should avoid headings and prefer clear line breaks/lists.
- Agent prompt policy requires entry retag/update proposals before tag-delete proposals when the tag is still referenced.
- Agent prompt policy requires parallel tool-call batches for independent read-only work, but proposal workflows should start with one representative `propose_*` call before scaling out to later batches.
- Agent system-prompt policy is organized into explicit markdown rule sections (tool discipline, proposal workflows, new proposal specifications, error handling, execution, final response).
- Agent system prompt renders `Current User Context` as fixed `Account Context`, `User Memory`, and `Entity Category Reference` subsections, with content-only inserts and `(none)` placeholders when a section has no content.
- Agent model/tool execution retries and limits can be overridden at runtime via `/settings`.
- Streamed model calls retry transient failures using the same retry policy.
- OpenRouter SSL `sslv3 alert bad record mac` transport failures get a one-shot immediate retry in both streamed and non-streamed model calls, even when `agent_retry_max_attempts=1`.
- Stream retries after partial output are de-duplicated so already-emitted prefixes are not re-sent to the SSE client.
- Tesseract OCR fallback depends on a local `tesseract` executable; if it is unavailable or OCR fails, PDF prompt text falls back to a no-content note while vision-capable models can still receive rendered page images.
- Agent model calls are routed through LiteLLM using the configured model string (`agent_model`), with credentials resolved from provider environment variables by default or optional runtime overrides (`agent_base_url`, `agent_api_key`) from `/settings`.
- `/settings` validates `agent_base_url` to allow only `http`/`https` URLs and blocks localhost domains plus non-public IP literals.
- Stored runtime `agent_api_key` overrides are plaintext in the local DB for this prototype; there is no application-layer encryption-at-rest yet.
- For models that support prompt caching, LiteLLM requests include explicit `cache_control_injection_points` anchored to system context and latest user turn (negative message index) so tool-loop steps can reuse cached prompt prefixes.
- Agent message uploads accept image and PDF attachments; each attachment now contributes its own model-visible text block (labeled with the uploaded filename when available), and the user's typed message is appended as the final text block after all attachment parts.
- PDF files first attempt normalized PyMuPDF text extraction, then fall back to local Tesseract OCR only when native extraction returns no usable text.
- When the configured model supports vision (via LiteLLM capability checks plus local overrides for known OpenRouter gaps such as `openrouter/qwen/qwen3.5-27b`), each uploaded PDF page is rendered and appended as image inputs immediately after that PDF's text block; non-PDF image uploads are also labeled and appended in attachment order before the trailing user prompt.
- Agent system prompts now embed the current `entity_category` taxonomy terms plus their descriptions (when present) as a reference section for entity normalization decisions.
- `list_tags` tool results now include both tag `type` and tag `description` in the model-visible tool output so tag semantics are available without a separate API read.
- Agent runs can be interrupted via `POST /api/v1/agent/runs/{run_id}/interrupt`; interrupted runs transition to `failed`.
- Thread deletion is available via `DELETE /api/v1/agent/threads/{thread_id}` and is blocked (`409`) while that thread has a running run.
- Thread summary rows from `GET /api/v1/agent/threads` now include `has_running_run` so the frontend can show per-thread active-run indicators.
- Thread deletion also removes that thread's persisted upload directories under `.data/agent_uploads/<message_id>/...`.
- Follow-up user turns after an interrupted run now include an interruption context note in model input so the agent treats the interrupted request as unfinished context.
- Agent message delivery now supports both modes:
  - async start + polling: `POST /api/v1/agent/threads/{thread_id}/messages`
  - SSE token stream: `POST /api/v1/agent/threads/{thread_id}/messages/stream`
- SSE streams now use `text_delta` plus `run_event`; `run_event.event_type` covers run start/finish, reasoning updates, and per-tool lifecycle transitions.
- Run tool-call payloads include lifecycle metadata (`llm_tool_call_id`, `started_at`, `completed_at`) plus a `has_full_payload` marker.
- `GET /api/v1/agent/threads/{thread_id}` now returns compact tool-call snapshots (`has_full_payload=false`; payload fields null) for faster timeline loads.
- Full tool payloads are available on demand via `GET /api/v1/agent/tool-calls/{tool_call_id}` (`has_full_payload=true`).
- Usage normalization maps provider-specific cache fields (`cached_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`) into run-level `cache_read_tokens` / `cache_write_tokens`.
- Agent runs persist nullable `context_tokens`; thread detail `current_context_tokens` now resolves from persisted run snapshots only (no load-time prompt rebuild/token recount).
- Observability context (`user`, `session_id=AgentThread.id`, run trace metadata) is propagated on each model call.
- When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are configured, LiteLLM `langfuse` success/failure callbacks are enabled and trace metadata is sent through LiteLLM `metadata`.
- Dashboard currency defaults to runtime settings (`/settings` override, else `BILL_HELPER_DASHBOARD_CURRENCY_CODE` / `CAD`).
- Benchmark and seed scripts use shared DB engine/session builders from `backend/database.py` to avoid lifecycle drift.

## Related Docs

- `docs/backend.md`
- `docs/api.md`
- `docs/data-model.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
