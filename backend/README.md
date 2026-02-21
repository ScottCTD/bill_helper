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
- `backend/services/runtime_settings.py`: persisted override + env fallback resolver for runtime settings.
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
- Entry-level `status` was removed; agent review state remains only on `agent_change_items`.
- Entry groups are derived from entry-link connected components; `/groups` is read-model only (no group create/update/delete endpoints).
- `GET /api/v1/groups` omits singleton components (`entry_count < 2`) to focus on linked groups.
- Agent tool contracts are name/selector-based (no domain IDs in model-facing arguments/outputs).
- Agent can emit sparse intermediate progress notes via `send_intermediate_update`; runtime streams these as `reasoning_update` SSE events.
- Entry create proposals can omit currency and fall back to the resolved runtime default currency (`/settings` override, else `BILL_HELPER_DEFAULT_CURRENCY_CODE`).
- Tag deletion proposals are blocked when the tag is still referenced by any non-deleted entries; apply path re-validates this constraint before delete.
- Agent prompt policy requires entry retag/update proposals before tag-delete proposals when the tag is still referenced.
- Agent model/tool execution retries and limits can be overridden at runtime via `/settings`.
- Streamed model calls retry transient failures using the same retry policy.
- OpenRouter SSL `sslv3 alert bad record mac` transport failures get a one-shot immediate retry in both streamed and non-streamed model calls, even when `agent_retry_max_attempts=1`.
- Stream retries after partial output are de-duplicated so already-emitted prefixes are not re-sent to the SSE client.
- Agent model calls are routed through LiteLLM using the configured model string (`agent_model`), and credentials are resolved from provider environment variables.
- Agent message uploads accept image and PDF attachments; PDF files are parsed to markdown text via MarkItDown before model calls.
- When the configured model supports vision (via LiteLLM capability checks), each uploaded PDF page is also rendered and sent as an image input.
- Agent runs can be interrupted via `POST /api/v1/agent/runs/{run_id}/interrupt`; interrupted runs transition to `failed`.
- Thread deletion is available via `DELETE /api/v1/agent/threads/{thread_id}` and is blocked (`409`) while that thread has a running run.
- Thread deletion also removes that thread's persisted upload directories under `.data/agent_uploads/<message_id>/...`.
- Follow-up user turns after an interrupted run now include an interruption context note in model input so the agent treats the interrupted request as unfinished context.
- Agent message delivery now supports both modes:
  - async start + polling: `POST /api/v1/agent/threads/{thread_id}/messages`
  - SSE token stream: `POST /api/v1/agent/threads/{thread_id}/messages/stream`
- SSE streams can include `text_delta`, `tool_call`, and `reasoning_update` events before terminal run status events.
- Observability context (`user`, `session_id=AgentThread.id`, run trace metadata) is propagated on each model call.
- When `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` are configured, LiteLLM `langfuse` success/failure callbacks are enabled and trace metadata is sent through LiteLLM `metadata`.
- Dashboard currency defaults to runtime settings (`/settings` override, else `BILL_HELPER_DASHBOARD_CURRENCY_CODE` / `CAD`).

## Related Docs

- `docs/backend.md`
- `docs/api.md`
- `docs/data-model.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
