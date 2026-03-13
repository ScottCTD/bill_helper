# Frontend Navigation

This file is intentionally thin. Canonical frontend documentation lives in `./docs/` with `../docs/frontend_index.md` as the cross-repo entry point.

## Canonical Docs

- `../docs/frontend_index.md`
- `./docs/README.md`
- `../docs/api.md`
- `../docs/development.md`
- `../docs/repository_structure.md`

## High-Frequency Paths

- `frontend/src/App.tsx`: route shell and lazy-loaded pages
- `frontend/src/pages/*`: route-level containers
- `frontend/src/features/*`: feature-owned state and composition
- `frontend/src/components/ui/*`: shared UI primitives
- `frontend/src/lib/*`: API client, types, query keys, invalidation
- `frontend/src/test/*`: shared test helpers

## When You Change Frontend Behavior

- Update the relevant `./docs/*.md` files and keep `../docs/frontend_index.md` current when the topic map changes.
- Update the relevant `../docs/feature-*.md` when UX or workflows changed.
- Update the relevant `../docs/api/*.md` files if the frontend now depends on new contract behavior.
- Keep `AGENTS.md` and the relevant skill docs in sync when the editing workflow changed.

## Verify

```bash
npm run test
npm run build
uv run python scripts/check_docs_sync.py
```
