# Backend Navigation

This file is intentionally thin. Canonical backend documentation lives in `../docs/backend.md`.

## Canonical Docs

- `../docs/backend.md`
- `../docs/backend/README.md`
- `../docs/api.md`
- `../docs/data-model.md`
- `../docs/repository-structure.md`

## High-Frequency Paths

- `backend/main.py`: app factory and route registration
- `backend/routers/*`: API endpoint layer
- `backend/services/*`: domain logic and agent runtime
- `backend/models_finance.py` and `backend/models_agent.py`: ORM contracts
- `backend/schemas_finance.py` and `backend/schemas_agent.py`: API contracts
- `backend/tests/*`: backend regression coverage

## When You Change Backend Behavior

- Update the relevant `../docs/backend/*.md` files and keep `../docs/backend.md` current when the topic map changes.
- Update the relevant `../docs/api/*.md` files for contract changes and keep `../docs/api.md` current when route-family navigation changes.
- Update `../docs/data-model.md` and `../docs/repository-structure.md` for schema or migration changes.
- Update the relevant `../docs/feature-*.md` when user-facing flows changed.

## Verify

```bash
uv run pytest
uv run python scripts/check_docs_sync.py
```
