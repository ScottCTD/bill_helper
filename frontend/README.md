# Frontend Guide

This module hosts the React app, route pages, UI primitives, and API/query client layer.

## Fast Entry Points

- Route shell: `frontend/src/App.tsx`
- Pages: `frontend/src/pages/*`
- Shared UI primitives: `frontend/src/components/ui/*`
- API layer: `frontend/src/lib/api.ts`
- Domain types: `frontend/src/lib/types.ts`
- Query keys/invalidation: `frontend/src/lib/queryKeys.ts`, `frontend/src/lib/queryInvalidation.ts`
- Styling tokens/components: `frontend/src/styles.css`

## File Map

- `frontend/src/pages/EntriesPage.tsx`: entry list/filter/table interactions.
- `frontend/src/components/EntryEditorModal.tsx`: entry create/edit modal.
- `frontend/src/pages/DashboardPage.tsx`: tabbed interactive analytics.
- `frontend/src/components/agent/*`: AI timeline and review UI.

## Common Change Paths

## 1) Entry Table or Editor UX

Touch together:

- `frontend/src/pages/EntriesPage.tsx`
- `frontend/src/components/EntryEditorModal.tsx`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/styles.css`

## 2) Dashboard UX

Touch together:

- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/lib/types.ts` (`Dashboard` shape)
- `frontend/src/lib/api.ts`
- `frontend/src/styles.css`

## 3) Shared Visual System

Touch together:

- `frontend/src/components/ui/*`
- `frontend/src/styles.css`
- `docs/frontend.md` (document new patterns)

## Run and Verify

```bash
npm install
npm run dev
npm run build
```

If backend/API contract changed, also run:

```bash
uv run --extra dev pytest
uv run python scripts/check_docs_sync.py
```

## Current Constraints

- Amount display uses code-prefix formatting (`CAD 8.13`).
- Entry status is not part of frontend entry models.
- Agent review timeline supports create/update/delete change items for entries, tags, and entities.
- Dashboard visualizations use Recharts and currently consume CAD-only analytics payloads.

## Related Docs

- `docs/frontend.md`
- `docs/api.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
