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
- `frontend/src/pages/EntryDetailPage.tsx`: entry-level detail and link controls with embedded group graph.
- `frontend/src/pages/GroupsPage.tsx`: derived group workspace (summary list, graph detail, and link operations).
- `frontend/src/components/EntryEditorModal.tsx`: entry create/edit modal.
- `frontend/src/components/LinkEditorModal.tsx`: shared link create modal used by entry detail and groups workspace.
- `frontend/src/components/GroupGraphView.tsx`: shared React Flow renderer for entry-group graphs.
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
- `frontend/src/features/properties/usePropertiesSectionState.ts`: active section/search/create-dialog UI state.
- `frontend/src/features/properties/usePropertiesFormState.ts`: properties CRUD form state.
- `frontend/src/features/properties/usePropertiesFilteredData.ts`: section-scoped filtered lists.
- `frontend/src/features/properties/sections/*.tsx`: section-specific UI for users/entities/tags/currencies/taxonomy terms.
- `frontend/src/pages/SettingsPage.tsx`: runtime configuration workspace for user overrides, including persistent agent memory.
- `frontend/src/components/agent/AgentPanel.tsx`: top-level coordinator for agent state/mutations and panel composition.
- `frontend/src/components/agent/AgentRunBlock.tsx`: run activity and summary rendering.
- `frontend/src/components/agent/activity.ts`: run/activity derivation helpers shared across agent UI.
- `frontend/src/components/agent/panel/*.tsx`: panel presentation modules (thread list, timeline, composer, usage bar, attachment preview dialog).
- `frontend/src/components/agent/panel/types.ts`: panel-local draft/optimistic message contracts.
- `frontend/src/components/agent/panel/format.ts`: date/thread/usage formatting helpers for panel UI.
- `frontend/src/components/agent/panel/useAgentDraftAttachments.ts`: attachment input/paste/drag-drop/preview state + handlers.
- `frontend/src/hooks/useResizablePanel.ts`: shared drag-to-resize hook for persistent sidebar and thread-rail widths.
- `frontend/src/components/agent/review/*`: run review modal and payload diff renderer.
- `frontend/src/components/agent/*.test.tsx`: agent UI unit tests.
- `frontend/src/components/agent/panel/AgentThreadList.test.tsx`: thread-list selection/delete interaction coverage.
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

## 7) Group Workspace / Graph UX

Touch together:

- `frontend/src/pages/GroupsPage.tsx`
- `frontend/src/pages/EntryDetailPage.tsx`
- `frontend/src/components/GroupGraphView.tsx`
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
npm audit
```

Operational impact:

- `npm audit` is the frontend dependency-health check for transitive advisories in the lockfile.
- The current lockfile resolves the recent `rollup` and `markdown-it` advisories with patched transitive versions.

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
- Entry groups are derived from link topology; there is no first-class group CRUD UI/API.
- Groups workspace reads from `/api/v1/groups` and `/api/v1/groups/{group_id}` and mutates topology only through link endpoints.
- Link creation in entry detail and groups workspace is modal-only (icon `+` action -> `LinkEditorModal`), with no inline link-create form.
- Link modal source/target entry fields use searchable single-select pickers for faster large-list selection.
- `/api/v1/groups` omits singleton components (`entry_count < 2`), so the list focuses on linked groups.
- On wide layouts, the left groups summary panel is viewport-bounded and scrolls internally so long group lists do not stretch overall page height.
- Graph rendering uses `reactflow` (pan/zoom/controls/minimap) via `GroupGraphView`.
- Runtime settings are loaded from `/api/v1/settings` and affect default currency/model behavior across pages.
- Runtime settings include an `Agent memory` textarea; when set, that text is attached to every backend agent system prompt.
- Agent review timeline supports create/update/delete change items for entries, tags, and entities.
- Agent review modal now renders CRUD-aware, field-level diffs (create/add, update delta, delete removal) instead of full payload snapshots.
- Entry proposal diff rows now use friendly field labels/order (`date`, `name`, `kind`, `amount`, `currency`, `from`, `to`, `tags`, `notes`) and human-readable amount values.
- Agent review `Approve All` uses a themed in-app confirmation dialog instead of browser-native confirm prompts.
- Agent review modal includes `Reject All` with confirmation; per-item `Approve & Next` is removed in favor of direct approve/reject + batch actions.
- Expanded tool-call details prioritize model-visible tool output text and keep structured JSON as secondary debug output.
- Agent home uses a dedicated right-pane timeline scroller while keeping the scrollbar at the panel edge (not beside message bubbles).
- The left thread rail is viewport-bounded with independent overflow scrolling and does not move when timeline content scrolls.
- Thread rows in the left rail are fixed-height, non-shrinking list items so long thread lists overflow and scroll instead of compressing.
- Thread rows now render a subtle running spinner badge when that thread has `has_running_run=true` from `GET /api/v1/agent/threads`.
- Thread rows expose a right-side delete control inside the same row box on hover/focus (always visible on touch devices) and call `DELETE /api/v1/agent/threads/{thread_id}` after a confirmation prompt.
- When thread deletion is temporarily disabled (for example, while a run is active), delete controls are hidden entirely to avoid misleading disabled clutter.
- Deleting the selected thread auto-selects the next thread when available; if none remain, the timeline returns to empty-selection state.
- The composer stays pinned at the bottom of the right pane; message input starts as one line and auto-expands up to a max height.
- Agent composer attachments support images and PDFs (picker, paste, and drag-drop paths); unsupported files are skipped with a local error.
- Draft and persisted PDF attachments render as file chips/links in timeline surfaces, while images continue to render as thumbnails.
- Agent message send uses backend SSE (`POST /api/v1/agent/threads/{thread_id}/messages/stream`) so assistant text appears incrementally in real time.
- Thread usage bar now shows `Context` as the current prompt context-window size for the selected thread, alongside cumulative `Total input`, `Output`, `Cache read`, `Cache hit rate`, and total cost.
- Token counters in the usage bar are compactly formatted as `x.xxK` to reduce horizontal space pressure.
- Streaming assistant activity now uses persisted `run.events` (`run_event` over SSE) so the same per-tool lifecycle timeline is visible live and after reload.
- Agent activity rendering is now strictly event-driven: `run.tool_calls` enrich visible tool rows, but the UI no longer reconstructs standalone activity rows from tool snapshots that lack matching `run.events`.
- Active SSE streams disable rapid thread polling; the UI falls back to slower recovery polling only when a run is still active without a healthy local stream.
- Thread detail returns compact tool-call rows (`has_full_payload=false`; payload fields null), and expanding a tool row triggers a one-off `GET /api/v1/agent/tool-calls/{tool_call_id}` hydration fetch.
- While a response is streaming, transient assistant text now renders inside the same collapsible Assistant/update bubble used by live activity (instead of a separate plain pending paragraph). When the matching `reasoning_update` (`source="assistant_content"`) arrives, that transient text buffer is cleared so the persisted update row becomes the authoritative version.
- The live Assistant/update bubble now becomes visible as soon as streaming starts (`run_started`), even before the first visible token or activity row exists; whitespace-only early `text_delta` chunks render as the same block-cursor placeholder (`▍`) instead of being suppressed until later content arrives.
- Runs that finish without a persisted assistant message (for example, an interrupted run) now render immediately after the user message that triggered them, instead of being appended at the bottom of the thread.
- During streaming, reasoning/update bubbles may auto-open, but tool rows stay collapsed by default so long tool runs do not keep forcing open the latest tool call.
- Expanded tool-call arguments and model-visible tool output now line-wrap instead of forcing horizontal scrolling on long single-line payloads.
- Optimistic user bubbles are reconciled against persisted timeline messages to avoid temporary duplicate user-message blocks during send.
- Route pages are lazy-loaded from `App.tsx` to keep initial bundle load bounded as feature count grows.
- The left app sidebar is collapsible and desktop-resizable via a shared drag handle; the expanded width persists to localStorage, while small-screen behavior stays fixed-width and slide-based.
- Agent run rendering and activity derivation are split from `AgentPanel.tsx` into dedicated modules to reduce coordinator complexity.
- Agent panel layout surfaces are further split into panel modules (`agent/panel/*`) to keep rendering concerns separate from orchestration logic.
- Agent home now uses a two-row header: title/actions on the first row and a single compact horizontal usage line on the second row.
- The right thread rail collapse now animates its width closed/open instead of disappearing instantly, and the composer sits slightly above the viewport edge instead of flush against the bottom.
- Thread-list rows use flex-centered labels and a tighter right-side delete affordance so the title text sits optically centered within each button.
- Accounts and properties pages now follow a feature-module split (page orchestrator + domain hook + section components) rather than single-file implementations.
- Properties model logic is decomposed into dedicated query/section-state/form/filter hooks for maintainable ownership boundaries.
- Accounts create/edit dialogs include optional markdown notes (`markdown_body`) using the shared markdown editor.
- Accounts no longer expose `institution`/`type` fields in table rows or create/edit dialogs.
- Properties create/edit flows are modal-driven for editable sections (`users`, `entities`, `tags`, and taxonomy terms); inline table-row create/edit forms are removed.
- Frontend tests are now first-class (`vitest` + Testing Library) with coverage over agent activity helpers, run block rendering, review diff generation, and accounts/properties page integration flows.
- Dashboard visualizations use Recharts, consume the backend-configured dashboard currency payload, exclude account-to-account transfer rows (account-category entities on both sides) from the displayed in/out analytics, and wait for measured card dimensions in `frontend/src/pages/DashboardPage.tsx` before mounting charts so route loads and tab switches avoid dev-time `-1 x -1` Recharts warnings.
- `frontend/src/pages/EntriesPage.tsx` now renders a compact `from -> to` subtitle under each entry name, with matching `.entries-name-*` styles in `frontend/src/styles.css` to keep long source/destination labels readable in the dense table.

## Related Docs

- `docs/frontend.md`
- `docs/api.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
- `docs/feature-account-reconciliation.md`
