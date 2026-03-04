# Backend Guide

This module hosts the FastAPI app, SQLAlchemy models, Pydantic schemas, and domain services.

## Fast Entry Points

- App startup: `backend/main.py`
- API routers: `backend/routers/*`
- Domain logic: `backend/services/*`
- Persistence model: `backend/models.py`
- API contracts: `backend/schemas.py`
- Tests: `backend/tests/*`

## File Map

- `backend/routers/entries.py`: entry CRUD, filters, link creation.
- `backend/routers/groups.py`: derived group summaries and graph detail read models.
- `backend/routers/dashboard.py`: monthly dashboard analytics endpoint.
- `backend/routers/agent.py`: agent thread/run/review endpoints.
- `backend/routers/settings.py`: runtime settings read/update endpoints.
- `backend/services/finance.py`: reconciliation + dashboard aggregations/projection.
- `backend/services/agent/change_apply.py`: apply approved proposals.
- `backend/services/runtime_settings.py`: persisted override + env fallback resolver for runtime settings, plus DB-backed `user_memory`.
- `backend/services/serializers.py`: ORM -> API schema conversion.

## Common Change Paths

## 1) Entry Contract Changes

Touch together:

- `backend/models.py`
- `backend/schemas.py`
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

- `backend/services/agent/change_apply.py`
- `backend/services/agent/review.py`
- `backend/services/agent/tools.py` (proposal/read outputs)
- `backend/tests/test_agent.py`

## 5) Agent Run Lifecycle / Interrupt Changes

Touch together:

- `backend/routers/agent.py`
- `backend/services/agent/runtime.py`
- `backend/tests/test_agent.py`

## 6) Runtime Settings Changes

Touch together:

- `backend/routers/settings.py`
- `backend/services/runtime_settings.py`
- runtime consumers (`backend/routers/*`, `backend/services/agent/*`) that depend on resolved settings
- `backend/schemas.py`
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
- Agent system prompt current-date context is rendered in `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` (default `America/Toronto`).
- Entry-level `status` was removed; agent review state remains only on `agent_change_items`.
- Entry groups are derived from entry-link connected components; `/groups` is read-model only (no group create/update/delete endpoints).
- `GET /api/v1/groups` omits singleton components (`entry_count < 2`) to focus on linked groups.
- Agent tool contracts are name/selector-based (no domain IDs in model-facing arguments/outputs).
- Entry selector/patch tool args are resilient to accidental nested JSON-object string encoding and normalize to objects before validation.
- Agent emits progress notes via `send_intermediate_update`; when a run needs tool calls, prompt policy requires it as the first tool call, and runtime streams successful calls as `reasoning_update` SSE events.
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
- Agent model calls are routed through LiteLLM using the configured model string (`agent_model`), and credentials are resolved from provider environment variables.
- For models that support prompt caching, LiteLLM requests include explicit `cache_control_injection_points` anchored to system context and latest user turn (negative message index) so tool-loop steps can reuse cached prompt prefixes.
- Agent message uploads accept image and PDF attachments; each attachment now contributes its own model-visible text block (labeled with the uploaded filename when available), and the user's typed message is appended as the final text block after all attachment parts.
- PDF files first attempt normalized PyMuPDF text extraction, then fall back to local Tesseract OCR only when native extraction returns no usable text.
- When the configured model supports vision (via LiteLLM capability checks plus local overrides for known OpenRouter gaps such as `openrouter/qwen/qwen3.5-27b`), each uploaded PDF page is rendered and appended as image inputs immediately after that PDF's text block; non-PDF image uploads are also labeled and appended in attachment order before the trailing user prompt.
- Agent system prompts now embed the current `entity_category` taxonomy terms plus their descriptions (when present) as a reference section for entity normalization decisions.
- `list_tags` tool results now include both tag `type` and tag `description` in the model-visible tool output so tag semantics are available without a separate API read.
- Agent runs can be interrupted via `POST /api/v1/agent/runs/{run_id}/interrupt`; interrupted runs transition to `failed`.
- Thread deletion is available via `DELETE /api/v1/agent/threads/{thread_id}` and is blocked (`409`) while that thread has a running run.
- Thread deletion also removes that thread's persisted upload directories under `.data/agent_uploads/<message_id>/...`.
- Follow-up user turns after an interrupted run now include an interruption context note in model input so the agent treats the interrupted request as unfinished context.
- Agent message delivery now supports both modes:
  - async start + polling: `POST /api/v1/agent/threads/{thread_id}/messages`
  - SSE token stream: `POST /api/v1/agent/threads/{thread_id}/messages/stream`
- SSE streams can include `text_delta`, `tool_call`, and `reasoning_update` events before terminal run status events.
- Run tool-call payloads include exact model-visible tool text (`output_text`) in addition to structured `output_json`.
- Usage normalization maps provider-specific cache fields (`cached_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`) into run-level `cache_read_tokens` / `cache_write_tokens`.
- Observability context (`user`, `session_id=AgentThread.id`, run trace metadata) is propagated on each model call.
- When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are configured, LiteLLM `langfuse` success/failure callbacks are enabled and trace metadata is sent through LiteLLM `metadata`.
- Dashboard currency defaults to runtime settings (`/settings` override, else `BILL_HELPER_DASHBOARD_CURRENCY_CODE` / `CAD`).

## Related Docs

- `docs/backend.md`
- `docs/api.md`
- `docs/data-model.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
