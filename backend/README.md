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

## 3) Agent Review Apply Changes

Touch together:

- `backend/services/agent/change_apply.py`
- `backend/services/agent/review.py`
- `backend/services/agent/tools.py` (proposal/read outputs)
- `backend/tests/test_agent.py`

## 4) Agent Run Lifecycle / Interrupt Changes

Touch together:

- `backend/routers/agent.py`
- `backend/services/agent/runtime.py`
- `backend/tests/test_agent.py`

## 5) Runtime Settings Changes

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

- Entry-level `status` was removed; agent review state remains only on `agent_change_items`.
- Agent tool contracts are name/selector-based (no domain IDs in model-facing arguments/outputs).
- Entry create proposals can omit currency and fall back to the resolved runtime default currency (`/settings` override, else `BILL_HELPER_DEFAULT_CURRENCY_CODE`).
- Tag deletion proposals are blocked when the tag is still referenced by any non-deleted entries; apply path re-validates this constraint before delete.
- Agent prompt policy requires entry retag/update proposals before tag-delete proposals when the tag is still referenced.
- Agent model/tool execution retries and limits can be overridden at runtime via `/settings`.
- Agent runs can be interrupted via `POST /api/v1/agent/runs/{run_id}/interrupt`; interrupted runs transition to `failed`.
- OpenRouter observability payload now includes stable `session_id=AgentThread.id` for each model call in a thread, which enables Langfuse/OpenRouter session grouping per conversation.
- Dashboard currency defaults to runtime settings (`/settings` override, else `BILL_HELPER_DASHBOARD_CURRENCY_CODE` / `CAD`).

## Related Docs

- `docs/backend.md`
- `docs/api.md`
- `docs/data-model.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
