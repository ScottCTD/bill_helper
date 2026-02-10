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
- `backend/services/finance.py`: reconciliation + dashboard aggregations/projection.
- `backend/services/agent/change_apply.py`: apply approved proposals.
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

## Run and Verify

```bash
uv run alembic upgrade head
uv run --extra dev pytest
uv run python scripts/check_docs_sync.py
```

## Current Constraints

- Entry-level `status` was removed; agent review state remains only on `agent_change_items`.
- Agent tool contracts are name/selector-based (no domain IDs in model-facing arguments/outputs).
- Entry create proposals can omit currency and fall back to `BILL_HELPER_DEFAULT_CURRENCY_CODE`.
- Agent model/tool execution retries are controlled by `BILL_HELPER_AGENT_RETRY_*` settings.
- Dashboard analytics are CAD-focused by design in the current implementation.

## Related Docs

- `docs/backend.md`
- `docs/api.md`
- `docs/data-model.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
