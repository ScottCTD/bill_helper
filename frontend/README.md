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
- `frontend/src/pages/AccountsPage.tsx`: account table workspace with create/edit dialogs, snapshots, and reconciliation.
- `frontend/src/pages/SettingsPage.tsx`: runtime configuration workspace for user overrides.
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

## 4) Runtime Settings UX

Touch together:

- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/queryKeys.ts`
- `frontend/src/lib/queryInvalidation.ts`
- dependent pages using configured defaults (`EntriesPage`, `EntryDetailPage`, `AccountsPage`, `DashboardPage`)

## 5) Accounts Workspace UX

Touch together:

- `frontend/src/pages/AccountsPage.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/queryKeys.ts`
- `frontend/src/lib/queryInvalidation.ts`
- `frontend/src/styles.css`

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
- Entries table date values are pinned to a no-wrap compact column to avoid split-date rows; horizontal table scroll handles overflow on smaller widths.
- Entries `Tag` and `Currency` filters are chip-based multi-select controls (`TagMultiSelect`) and apply local row filtering for selected values.
- Entries filter controls use consistent baseline sizing/chrome across `Kind`, `Tags`, `Currencies`, and `Source text`.
- Entry status is not part of frontend entry models.
- Runtime settings are loaded from `/api/v1/settings` and affect default currency/model behavior across pages.
- Agent review timeline supports create/update/delete change items for entries, tags, and entities.
- Agent review modal now renders CRUD-aware, field-level diffs (create/add, update delta, delete removal) instead of full payload snapshots.
- Agent review `Approve All` uses a themed in-app confirmation dialog instead of browser-native confirm prompts.
- Agent home uses a dedicated right-pane timeline scroller while keeping the scrollbar at the panel edge (not beside message bubbles).
- The left thread rail is viewport-bounded with independent overflow scrolling and does not move when timeline content scrolls.
- The composer stays pinned at the bottom of the right pane; message input starts as one line and auto-expands up to a max height.
- Agent message send uses backend SSE (`POST /api/v1/agent/threads/{thread_id}/messages/stream`) so assistant text appears incrementally in real time.
- Optimistic user bubbles are reconciled against persisted timeline messages to avoid temporary duplicate user-message blocks during send.
- Dashboard visualizations use Recharts and consume the backend-configured dashboard currency payload.

## Related Docs

- `docs/frontend.md`
- `docs/api.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
- `docs/feature-account-reconciliation.md`
