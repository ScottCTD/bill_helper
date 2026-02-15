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
- Test config: `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`

## File Map

- `frontend/src/pages/EntriesPage.tsx`: entry list/filter/table interactions.
- `frontend/src/components/EntryEditorModal.tsx`: entry create/edit modal.
- `frontend/src/pages/DashboardPage.tsx`: tabbed interactive analytics.
- `frontend/src/pages/AccountsPage.tsx`: thin page orchestrator for accounts feature modules.
- `frontend/src/features/accounts/useAccountsPageModel.ts`: account queries/mutations/form state orchestration.
- `frontend/src/features/accounts/AccountsTableSection.tsx`: account list/search/selection section UI.
- `frontend/src/features/accounts/ReconciliationSection.tsx`: reconciliation panel UI.
- `frontend/src/features/accounts/SnapshotsSection.tsx`: snapshot form/history panel UI.
- `frontend/src/features/accounts/AccountDialogs.tsx`: create/edit account dialog UI.
- `frontend/src/pages/PropertiesPage.tsx`: thin page orchestrator for property catalogs.
- `frontend/src/features/properties/usePropertiesPageModel.ts`: properties page coordinator that composes queries/state/mutations hooks.
- `frontend/src/features/properties/usePropertiesQueries.ts`: properties queries + taxonomy display/option derivation.
- `frontend/src/features/properties/usePropertiesSectionState.ts`: active section/search/create-panel UI state.
- `frontend/src/features/properties/usePropertiesFormState.ts`: properties CRUD form state.
- `frontend/src/features/properties/usePropertiesFilteredData.ts`: section-scoped filtered lists.
- `frontend/src/features/properties/sections/*.tsx`: section-specific UI for users/entities/tags/currencies/taxonomy terms.
- `frontend/src/pages/SettingsPage.tsx`: runtime configuration workspace for user overrides.
- `frontend/src/components/agent/AgentPanel.tsx`: top-level coordinator for agent state/mutations and panel composition.
- `frontend/src/components/agent/AgentRunBlock.tsx`: run activity and summary rendering.
- `frontend/src/components/agent/activity.ts`: run/activity derivation helpers shared across agent UI.
- `frontend/src/components/agent/panel/*.tsx`: panel presentation modules (thread list, timeline, composer, usage bar, attachment preview dialog).
- `frontend/src/components/agent/panel/types.ts`: panel-local draft/optimistic message contracts.
- `frontend/src/components/agent/panel/format.ts`: date/thread/usage formatting helpers for panel UI.
- `frontend/src/components/agent/panel/useAgentDraftAttachments.ts`: attachment input/paste/drag-drop/preview state + handlers.
- `frontend/src/components/agent/review/*`: run review modal and payload diff renderer.
- `frontend/src/components/agent/*.test.tsx`: agent UI unit tests.
- `frontend/src/pages/AccountsPage.test.tsx`, `frontend/src/pages/PropertiesPage.test.tsx`: page-level integration tests for workspace flows.
- `frontend/src/test/renderWithQueryClient.tsx`: reusable query-client test renderer.
- `frontend/src/test/factories/agent.ts`: shared typed test fixtures for agent domain models.

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
- `frontend/src/features/accounts/*`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/queryKeys.ts`
- `frontend/src/lib/queryInvalidation.ts`
- `frontend/src/styles.css`

## 6) Properties Workspace UX

Touch together:

- `frontend/src/pages/PropertiesPage.tsx`
- `frontend/src/features/properties/*`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/queryKeys.ts`
- `frontend/src/lib/queryInvalidation.ts`
- `frontend/src/styles.css`

## Run and Verify

```bash
npm install
npm run dev
npm run test
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
- Streaming assistant activity now supports interleaved reasoning updates (`reasoning_update`) plus grouped tool-call traces, and the same interleaved trace remains visible after run completion.
- Optimistic user bubbles are reconciled against persisted timeline messages to avoid temporary duplicate user-message blocks during send.
- Route pages are lazy-loaded from `App.tsx` to keep initial bundle load bounded as feature count grows.
- Agent run rendering and activity derivation are split from `AgentPanel.tsx` into dedicated modules to reduce coordinator complexity.
- Agent panel layout surfaces are further split into panel modules (`agent/panel/*`) to keep rendering concerns separate from orchestration logic.
- Accounts and properties pages now follow a feature-module split (page orchestrator + domain hook + section components) rather than single-file implementations.
- Properties model logic is decomposed into dedicated query/section-state/form/filter hooks for maintainable ownership boundaries.
- Frontend tests are now first-class (`vitest` + Testing Library) with coverage over agent activity helpers, run block rendering, review diff generation, and accounts/properties page integration flows.
- Dashboard visualizations use Recharts and consume the backend-configured dashboard currency payload.

## Related Docs

- `docs/frontend.md`
- `docs/api.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
- `docs/feature-account-reconciliation.md`
