# Frontend Documentation

## Stack

- React 19
- TypeScript
- Vite
- React Router
- TanStack Query
- Recharts
- React Flow
- Tailwind CSS
- `shadcn/ui` component primitives
- Radix UI primitives (Dialog/Select/Checkbox/Label/Slot)

## Build and Runtime

- Dev server: `npm run dev` (default `http://localhost:5173`)
- Frontend tests: `npm run test`
- Production build: `npm run build`
- API base override: `VITE_API_BASE_URL` (optional)

## App Shell and Routing

Defined in `frontend/src/App.tsx`.

Current shell behavior:

- collapsible left sidebar (`Sidebar.tsx`) with vertical navigation links (`Agent`, `Dashboard`, `Entries`, `Groups`, `Accounts`, `Properties`, `Settings`)
- sidebar shows app title, icon+label nav links, and a footer tagline; collapses to icon-only mode via toggle button
- content canvas is route-driven (no global right-side agent occupancy on non-home pages)
- home route is AI-native and renders the agent experience as full-height primary page content (bypasses app-content padding to fill the viewport)
- route pages are lazy-loaded via `React.lazy` + `Suspense` so non-home routes are not eagerly loaded into the initial JS payload
- page sections are visually separated; readable container width tuned for full-page content
- responsive behavior:
  - on small screens (≤768px) the sidebar starts collapsed to icon-only and can slide open

Pages:

- `/` -> AI home chat
- `/dashboard` -> dashboard analytics
- `/entries` -> entry list
- `/entries/:entryId` -> entry detail
- `/groups` -> derived group workspace (summary + graph + link operations)
- `/accounts` -> accounts
- `/properties` -> core catalogs + taxonomy term management
- `/settings` -> runtime settings workspace

Providers in `frontend/src/main.tsx`:

- `QueryClientProvider`
- `BrowserRouter`

## Shared Client Layer

## `frontend/src/lib/types.ts`

Defines typed API models for:

- ledger domain (`Entry`, `Account`, `User`, `Entity`, `Tag`, ...)
- analytics (`Dashboard`, `Reconciliation`, ...)
- runtime settings domain (`RuntimeSettings`, `RuntimeSettingsOverrides`)
- agent domain (`AgentThread*`, `AgentMessage*`, `AgentRun`, `AgentToolCall`, `AgentChangeItem`, `AgentReviewAction`)

## `frontend/src/lib/api.ts`

Responsibilities:

- generic `request<T>` helper
- JSON and FormData request handling
- endpoint functions for all backend domains including `agent/*`
- runtime settings client methods:
  - `getRuntimeSettings`
  - `updateRuntimeSettings`
- taxonomy client methods:
  - `listTaxonomies`
  - `listTaxonomyTerms`
  - `createTaxonomyTerm`
  - `updateTaxonomyTerm`
- group client methods:
  - `listGroups`
  - `getGroup`

## `frontend/src/lib/queryKeys.ts`

Responsibilities:

- centralized TanStack Query key factory by domain
- stable key shapes for list/detail/thread/account-derived queries
- avoids ad-hoc string arrays across pages/components
- groups domain includes:
  - `groups.list`
  - `groups.detail(groupId)`
- properties domain includes dedicated taxonomy keys:
  - `properties.taxonomies`
  - `properties.taxonomyTermsRoot`
  - `properties.taxonomyTerms(taxonomyKey)`
- settings domain includes:
  - `settings.runtime`

## `frontend/src/lib/queryInvalidation.ts`

Responsibilities:

- centralized invalidation policies after writes/review actions
- shared invalidation bundles for entry/account/agent/property read-model refresh
- runtime settings invalidation bundle:
  - `invalidateRuntimeSettingsReadModels(queryClient)` to refresh dependent surfaces after settings writes
- reduces duplicated cache-invalidation logic across screens
- taxonomy-aware invalidation now includes:
  - assignment-driven term usage refresh when tags/entities change
  - `invalidateTaxonomyReadModels(queryClient, taxonomyKey?)` for term create/rename and dependent lists

Agent client methods:

- `listAgentThreads`
- `createAgentThread`
- `deleteAgentThread`
- `getAgentThread`
- `streamAgentMessage`
- `interruptAgentRun`
- `getAgentRun`
- `approveAgentChangeItem`
- `rejectAgentChangeItem`

## Page/Container Responsibilities

## `EntriesPage.tsx`

- list/filter entries
- open unified entry popup for create/edit via row double-click
- delete entry
- creation action is a compact `+` button placed beside the `Source text` filter
- `Tag` and `Currency` filters now use `TagMultiSelect` chip controls with multi-selection behavior
- selected tag/currency filters are applied client-side on fetched rows (OR semantics within each filter group)
- no separate top entry-creation card
- group column only renders explicit group names; UUID-only unnamed groups are hidden
- table row density is compacted and delete action is de-emphasized
- tags column renders tag names as compact bubble chips instead of comma-separated text
- popup property rows use compact inline `Label: control` formatting for tighter scanability
- `Kind / Amount / Currency` and `From / To` rows are tuned to remain single-line in desktop popup width
- `Owner` row is constrained to single-line in desktop popup width
- `Status` has been removed from entry create/edit/list/filter UI and from entry payloads
- entry create modal default currency now resolves from runtime settings (`GET /settings`)
- `Kind` table cell uses symbol-only indicators (`+` for income, `-` for expense)
- amount cells render compact numeric precision in the entries list (`300.00 -> 300`, `300.20 -> 300.2`, `300.25 -> 300.25`) with a de-emphasized ISO currency label
- now uses shared shadcn primitives for card layout, filters, badges, and table actions
- date column uses a fixed compact width with no-wrap so ISO dates stay single-line; narrow viewports scroll horizontally instead of wrapping
- filter toolbar now uses shared table-shell classes aligned with `Properties`:
  - `.table-toolbar`
  - `.table-toolbar-filters`
  - `.table-toolbar-action`

## `EntryDetailPage.tsx`

- entry details and group graph
- link create/delete with modal creation flow (icon `+` opens shared `LinkEditorModal`)
- source/target entry pickers in link modal use searchable `SingleSelect` controls
- includes shortcut action to open the dedicated groups workspace
- uses shared popup editor for edits (same auto-save behavior as entries list popup)
- now uses shared shadcn primitives for cards, action buttons, and link editor modal controls
- editor wiring also consumes runtime settings defaults for consistency with create flow

## `GroupsPage.tsx`

- dedicated derived-group workspace (`/groups`)
- left summary list sourced from `GET /groups` (linked groups only; `entry_count >= 2`)
- selected group graph detail sourced from `GET /groups/{group_id}`
- link operation panel for group-shape mutations using existing link endpoints:
  - create: icon `+` action opens `LinkEditorModal`, submits `POST /entries/{entry_id}/links`
  - delete: `DELETE /links/{link_id}`
- entry member table for the selected graph component
- group operations are link-driven only (no first-class group CRUD UI)

## `AccountsPage.tsx`

- page is now a thin orchestrator; domain state/actions live in `frontend/src/features/accounts/useAccountsPageModel.ts`
- accounts workspace UI is split into dedicated section components:
  - `frontend/src/features/accounts/AccountsTableSection.tsx`
  - `frontend/src/features/accounts/ReconciliationSection.tsx`
  - `frontend/src/features/accounts/SnapshotsSection.tsx`
  - `frontend/src/features/accounts/AccountDialogs.tsx`
- table-first account workspace aligned with Entries/Properties table shell patterns
- compact toolbar with search and icon-only `+` action for account creation
- create account via modal dialog (`Dialog` + shared form primitives)
- per-row `Edit` action opens modal dialog for account updates (including active/inactive toggle)
- account dialogs now edit `Owner`, `Name`, `Currency`, `Notes`, and `Active`; legacy `institution`/`type` fields are removed
- account create/edit dialogs include optional markdown notes (`markdown_body`) via `MarkdownBlockEditor`
- account notes editor is mounted as a direct editable surface in dialogs (not wrapped by form-label containers) so caret/focus editing works reliably
- selected table row drives snapshot create/history and reconciliation side panels
- both side panels include plain-language helper copy so terms are understandable in-product:
  - reconciliation definitions for `As of`, `Ledger`, `Snapshot`, `Delta`
  - snapshot form definitions for `Snapshot date`, `Balance`, and optional `Note`
- reconciliation copy explicitly documents runtime behavior:
  - ledger balance is computed from entries up to `as_of`
  - snapshot balance uses the latest snapshot with `snapshot_at <= as_of`
  - `delta = ledger - snapshot`
- create-account default currency resolves from runtime settings (`GET /settings`)

## `PropertiesPage.tsx`

- page is now a thin orchestrator; domain state/actions live in `frontend/src/features/properties/usePropertiesPageModel.ts`
- properties model internals are split into focused hooks:
  - `frontend/src/features/properties/usePropertiesQueries.ts` (queries + taxonomy option/label derivation)
  - `frontend/src/features/properties/usePropertiesSectionState.ts` (active section/search/create-dialog UI state)
  - `frontend/src/features/properties/usePropertiesFormState.ts` (CRUD form/editing state)
  - `frontend/src/features/properties/usePropertiesFilteredData.ts` (section-specific filtered lists)
- section UI is split by concern under `frontend/src/features/properties/sections/*`:
  - `UsersSection.tsx`
  - `EntitiesSection.tsx`
  - `TagsSection.tsx`
  - `CurrenciesSection.tsx`
  - `TaxonomyTermsSection.tsx`
- two-level information architecture:
  - `Core`: Users, Entities, Tags, Currencies
  - `Taxonomies`: Entity Categories, Tag Categories
- left rail section switching (stacks into wrapped segmented groups on smaller screens)
- one active table surface at a time instead of one long vertical section wall
- shared table shell per section:
  - title/subtitle row
  - unified filter toolbar
  - compact right-aligned `+` add action for editable sections
- create and edit interactions are modal-driven across editable sections (`users`, `entities`, `tags`, `entity categories`, `tag categories`):
  - `+` opens create dialog
  - row `Edit`/`Rename` opens edit dialog
  - no inline row edit/create panels in the table body
- taxonomy term CRUD tables:
  - `Entity Categories`: name, usage count, rename
  - `Tag Categories`: name, usage count, rename
- entities/tags category fields now use taxonomy-sourced creatable pickers
- currencies remain read-only in this iteration

## `DashboardPage.tsx`

- tabbed interactive analytics surface (`Overview`, `Daily Spend`, `Breakdowns`, `Insights`)
- uses Recharts for bar/area/pie plots with tooltips and legends
- runtime-configured dashboard currency analytics (non-matching currency entries are excluded)
- daily vs non-daily expense segmentation:
  - `daily` tag marks an expense as daily
  - `non-daily` (or `non_daily` / `nondaily`) overrides and marks non-daily
- overview panel:
  - monthly expense/income/net cards
  - daily-vs-non-daily pie split
  - current-month projection card
- daily panel:
  - daily-tagged average/median stats
  - selected-month daily area chart
  - monthly daily/non-daily trend chart
- breakdowns panel:
  - spending by tags, `to`, and `from`
- insights panel:
  - weekday spend bar chart
  - largest expenses table
  - configured-currency reconciliation table

## `SettingsPage.tsx`

- categorized runtime settings workspace with responsive card layout:
  - `General` (current user name, default currency, dashboard currency)
  - `Agent Runtime` (model, step/image limits)
  - `Reliability` (retry policy controls)
- top summary surface shows active model
- supports save/update and reset-to-server-default flows
- setting changes trigger cache invalidation across dependent pages (agent/dashboard/accounts/entries/users)

## Agent UI

## `frontend/src/components/agent/AgentPanel.tsx`

Used as the primary AI page (`/`) via `frontend/src/pages/HomePage.tsx`.

This file now acts as the stateful coordinator. Run activity rendering and derivation logic were extracted to:

- `frontend/src/components/agent/AgentRunBlock.tsx`
- `frontend/src/components/agent/activity.ts`
- panel rendering surfaces were further extracted to:
  - `frontend/src/components/agent/panel/AgentThreadList.tsx`
  - `frontend/src/components/agent/panel/AgentTimeline.tsx`
  - `frontend/src/components/agent/panel/AgentComposer.tsx`
  - `frontend/src/components/agent/panel/AgentThreadUsageBar.tsx`
  - `frontend/src/components/agent/panel/AgentAttachmentPreviewDialog.tsx`
  - `frontend/src/components/agent/panel/useAgentDraftAttachments.ts`
  - `frontend/src/components/agent/panel/types.ts`
  - `frontend/src/components/agent/panel/format.ts`

Timeline features:

- left conversation history rail (thread list) with compact one-line thread buttons
- thread label uses the first 20 characters of the thread title (thread titles are seeded from the first user message)
- thread list uses plain list-row styling for non-selected items; only the active thread is boxed/highlighted
- thread rows expose a right-side delete icon button inside the same row box on hover/focus (always visible on touch devices)
- thread delete action confirms intent in the panel, then calls `DELETE /api/v1/agent/threads/{thread_id}`
- deleting a selected thread automatically selects the next available thread (or clears selection when none remain)
- click-to-open conversation behavior from history rail
- creating a new thread via `New Thread` focuses the composer textarea for immediate typing
- header title includes active model context (`Agent (<model>)`) based on the most recent run in the selected thread
- main chat timeline with user/assistant message bubbles
- timeline scroll behavior is a dedicated right-pane scroll surface with scrollbar at panel edge
- desktop thread rail is viewport-bounded and keeps its own independent overflow scroll
- assistant/system message bodies render markdown via `react-markdown` + `remark-gfm` (sanitized defaults, GFM tables/task lists/strikethrough)
- attachment previews for uploaded images and PDF files
- run blocks are anchored to assistant-side timeline events (`assistant_message_id`) to keep tool activity in assistant flow
- active runs without an assistant message render only when there is visible activity payload (tool calls/errors/review summary)
- running assistant bubbles interleave `send_intermediate_update` reasoning notes with grouped non-update tool-call batches
- completed runs retain the same interleaved reasoning/tool-batch structure for consistency with in-flight rendering
- tool-call traces now use two-level disclosure:
  - outer run-level toggle (`N tool calls`)
  - inner per-tool toggle (input/output JSON)
- during active execution, outer tool-batch collapse is intentionally disabled to avoid flicker while batches are growing
- a rotating chevron icon indicates the expand/collapse state of each tool call
- expanded tool-call details are indented with a left border line for visual hierarchy
- message and tool-call timestamps are hidden by default and fade in on hover for a cleaner look
- the composer shares the same horizontal padding as the conversation area (no extra inset)
- while send/run is in-flight, timeline polling stays active so tool-call progress can appear before final assistant text
- assistant message cards render run/tool activity before assistant markdown content, so final text appears after tool-call context
- in-flight run cards do not render separate `Run: running (...)` header/timestamp rows; activity is shown via thinking/tool traces only
- when a run has review items, the review request/action block renders below the assistant message content
- completed assistant messages no longer render per-message run metadata rows (`Run: completed ...`)
- cumulative thread usage/cost bar is shown once above the composer:
  - `Input`, `Output`, `Cache read`, `Cache write`
  - rightmost `Total cost` (USD; computed from backend LiteLLM pricing fields)
- run-level proposal summary cards:
  - pending copy (`N proposed changes pending review`)
  - primary action (`Click to review proposed changes`)
  - metadata chips (`Entry xN`, `Tag xN`, `Entity xN`)
  - inline failed-apply warning when a run contains `APPLY_FAILED` items

Review actions:

- handled in a dedicated run-scoped review modal (`frontend/src/components/agent/review/AgentRunReviewModal.tsx`)
- modal behavior:
  - one scrollable column with stacked proposal blocks in run order
  - focused pending block is tracked by `IntersectionObserver`
  - CRUD-aware field-level diff rendering (`frontend/src/components/agent/review/diff.ts`):
    - create proposals render additive `+` field lines
    - update proposals render changed fields only (`-` old / `+` new)
    - delete proposals render removed `-` field lines for the target identity/resource payload
  - reviewer-edited create-entry JSON still renders paired `-`/`+` lines against the original payload
  - per-proposal stat badges (`Changed`, `Added`, `Removed`) and compact metadata pills (target/selector/patch scope/impact counts)
  - supports labeled proposal blocks for entry/tag/entity create/update/delete types
  - entry create proposals support edit-before-approve via JSON override textarea
- sticky action bar:
  - `Reject` (focused pending item)
  - `Approve` (focused pending item)
  - `Approve & Next` (focused item, then smooth-scroll/focus next pending item after current index)
  - `Approve All` opens an in-app themed confirmation dialog (no browser `window.confirm`)
  - confirmed `Approve All` sequentially applies all pending items in deterministic order and continues through failures
  - pending context text (`Pending X of Y`) and focused ordinal
- apply-failure handling:
  - failures are surfaced inline on proposal blocks
  - `Approve All` shows `Applied X / Failed Y` summary with quick-jump links to failed items

Composer:

- card-style input box: borderless textarea inside a rounded container with a bottom toolbar row
- composer bar is pinned at the bottom of the right pane while timeline content scrolls
- textarea defaults to a single line and auto-grows with content up to a bounded max height, then becomes internally scrollable
- toolbar contains an "Add Attachments" button (paperclip icon, triggers hidden file input) and a run-aware primary action:
  - idle: `Send`
  - assistant busy (active run or active SSE stream): destructive `Stop` (aborts stream request and interrupts run if still active)
- compact removable attachment chips above the composer box (image thumbnails and PDF file chips with extra-small corner remove buttons)
- click-to-preview attachment dialog before send (image and PDF)
- composer submit shortcut is line-aware:
  - `Cmd+Enter` (or `Ctrl+Enter`) always submits
  - plain `Enter` submits only when the draft is a single line
- paste image/PDF attachments directly into the composer (`Cmd/Ctrl+V`)
- drag-and-drop image/PDF files onto the composer drop target
- optimistic user message rendering: user bubble appears immediately after submit, before run completion
- optimistic user bubble is auto-removed once the persisted server-side user message arrives, preventing temporary duplicate user blocks
- optimistic assistant placeholder rendering: assistant bubble appears immediately after submit (without waiting for run-status polling) with a flashing block cursor (`▍`) while awaiting first assistant content/activity
- assistant response text is streamed from backend SSE in real time (`POST /api/v1/agent/threads/{thread_id}/messages/stream`)
- streamed assistant bubble remains visible while tool-call activity cards are also shown, so token deltas are not hidden during long multi-tool runs
- stream event activity (`tool_call` + `reasoning_update`) for the active run is rendered inside the same streaming assistant bubble (instead of a second temporary assistant bubble)
- optimistic assistant bubble is reconciled away as soon as a new persisted assistant message arrives, preventing split-then-merge visual artifacts
- active-run polling refreshes timeline state while backend run status is `running`

Layout mode: full-page AI home experience (drawer mode has been removed).

Cache invalidation after review apply:

- handled through `invalidateEntryReadModels` + `invalidateAgentThreadData`
- refreshes `entries`, `dashboard`, `tags`, `entities`, `users`, `currencies`, and agent thread views
- run review modal actions call existing per-item approve/reject endpoints; no new backend review endpoint was required

## Existing Shared Components

- `EntryEditorModal.tsx`
- `SingleSelect.tsx`
- `CreatableSingleSelect.tsx`
- `TagMultiSelect.tsx`
- `MarkdownBlockEditor.tsx`
- `LinkEditorModal.tsx`
- `GroupGraphView.tsx` (React Flow-based graph renderer shared by entry detail and groups workspace)
- `MetricCard.tsx`
- `ui/MarkdownRenderer.tsx`
- `agent/AgentRunBlock.tsx`
- `agent/activity.ts`
- `agent/review/AgentRunReviewModal.tsx`
- `agent/review/diff.ts`
- `components/ui/*` (new shadcn-based primitive layer)
  - `button.tsx`, `card.tsx`, `dialog.tsx`, `input.tsx`, `textarea.tsx`, `badge.tsx`, `table.tsx`, `select.tsx`, `checkbox.tsx`, `label.tsx`, `separator.tsx`, `native-select.tsx`
  - `NativeSelect` now supports wrapper-level sizing via `wrapperClassName` so narrow controls keep caret alignment

## Feature Modules

- `features/accounts/*`
- `features/properties/*`
- `agent/panel/*`

## Styling (`frontend/src/styles.css`)

Includes:

- Tailwind base/components/utilities imports
- CSS variable token layer (`--background`, `--foreground`, `--primary`, `--border`, `--ring`, `--success`, etc.)
  - base app background/surfaces now default to white with restrained neutral accents
- global UI typography uses a product-style sans stack (`Inter` -> SF Pro -> Segoe UI/Roboto fallbacks) instead of editorial/body-copy-first styling
- component classes for legacy/transitioned surfaces (`.card`, `.form-grid`, `.field`, `.agent-panel`, `.tag-multiselect`, editor/chart helpers)
- group workspace and React Flow styling hooks:
  - `.groups-layout`
  - `.groups-summary-*`
  - `.group-flow-*`
- entries filter `TagMultiSelect` controls now share the same baseline chrome (height/padding/focus/hover treatment) as adjacent select/input filters
- shared table surface classes:
  - `.table-shell*`
  - `.table-toolbar*`
  - `.table-inline-form*`
- shared properties workspace classes:
  - `.properties-layout`
  - `.properties-nav*`
  - `.properties-panel`
- compact entries table row classes and muted action styling for less visual noise
- entry popup classes now model a vertical, scrollable page layout (properties + seamless markdown editor)
- entry popup now uses fixed viewport height and popup-level scrolling for long note content
- entry property layout classes support inline `Label: control` rows and grouped compact controls
- `Owner` property row is now single-surface (status selector removed)
- creatable single-select styles are used for typed+dropdown entity inputs to stay visually aligned with other popup controls
- creatable entity combobox text input is explicitly borderless so only the outer control border is rendered
- popup header vertical spacing is reduced to tighten distance from title to first property row
- dialog content uses flex-column layout (instead of grid) to avoid stretched empty space in fixed-height popup
- dialog content positioning avoids transform-centering to reduce floating toolbar offset issues in embedded editors
- single-select control styling for `Kind` to align with other property controls
- symbol-only kind indicators (`.kind-indicator*`) for compact income/expense table rendering
- dashboard tab button classes (`.dashboard-tab-*`) for section switching
- responsive shell/agent behavior
- agent timeline refresh for workspace redesign:
  - single-surface message body styling (no nested inner message box)
  - markdown typography for assistant/system output (including list marker rendering)
  - lightweight bullet-list tool-call display with chevron expand/collapse
  - draft attachment chip + preview dialog styling
  - cumulative thread usage/cost bar styling above composer
- button baseline behavior is scoped to unclassed legacy buttons so `shadcn/ui` variant buttons are not overridden
- spacing scale was relaxed (`app-content`, `stack`, `grid`, form gaps) to reduce crowded coupling between sections
- accounts page now uses shared table + dialog primitives instead of bespoke chip-picker controls
- amount formatting now uses code-prefix formatting in UI (`<CURRENCY_CODE> <amount>`)
- scrollbar system now uses tokenized Notion-like styling:
  - thin rounded thumbs
  - subtle hover contrast
  - transparent tracks
  - shared `.scroll-surface` hook for internal scroll containers (tables/dialog content)
- layout-jitter mitigation:
  - document-level `scrollbar-gutter: stable` on `html`
  - `.scroll-surface` containers also use stable gutter so popup/table width does not shift when overflow toggles

## Design System and Config

- Tailwind config: `frontend/tailwind.config.ts`
- PostCSS config: `frontend/postcss.config.js`
- shadcn manifest: `frontend/components.json`
- utility merge helper: `frontend/src/lib/utils.ts`

Operationally, frontend styling now depends on Tailwind build-time generation and the shared token variables in `frontend/src/styles.css`.

## Operational Impact

- frontend now depends on group read-model APIs for the groups workspace:
  - `GET /groups`
  - `GET /groups/{group_id}`
- frontend now depends on agent API contracts and attachment URLs
- multipart requests are required for agent message send with image/PDF attachments
- agent send now depends on SSE parsing for incremental assistant text events (`run_started`, `text_delta`, `tool_call`, `reasoning_update`, `run_completed`, `run_failed`)
- all query keys/invalidation rules are now centralized, so new pages/features should reuse `queryKeys` + `queryInvalidation` helpers
- UI primitives should be sourced from `frontend/src/components/ui/*` before introducing one-off controls/styles
- page-level integration tests now cover accounts/properties orchestration flows:
  - `frontend/src/pages/AccountsPage.test.tsx`
  - `frontend/src/pages/PropertiesPage.test.tsx`
  - shared wrapper: `frontend/src/test/renderWithQueryClient.tsx`
- properties page now issues taxonomy reads in addition to users/entities/tags/currencies:
  - `GET /taxonomies`
  - `GET /taxonomies/entity_category/terms`
  - `GET /taxonomies/tag_category/terms`
- accounts workspace now uses table-row selection with dialog-based create/edit:
  - create action is the icon `+` button in the table toolbar
  - edits are per-row and open from `Edit` action buttons
  - snapshot/reconciliation panels reflect the currently selected row
- properties workspace create/edit actions are dialog-based across editable sections:
  - `+` triggers section create dialogs
  - row `Edit`/`Rename` triggers section edit dialogs
  - inline table-row form editing is removed
- taxonomy term create/rename and entity/tag category assignment changes now invalidate taxonomy-term usage caches
- entry popup save flow is now close-driven:
  - clicking outside/closing attempts to auto-save when there are changes
  - clean/no-change close exits immediately without write calls
- entry popup no longer sends `account_id` in create/edit payloads; `From`/`To` entity fields are the primary relation inputs
- `From`/`To` fields now accept typed values with entity suggestions:
  - exact match to existing entity name -> sends `from_entity_id` / `to_entity_id`
  - non-matching typed name -> sends `from_entity` / `to_entity` so backend creates the entity
  - non-empty typed values always render an explicit `Create entity "..."` option in the entity dropdown
  - created entity options are shared across both `From` and `To` dropdowns during the current edit session
- `Tags` input remains creatable with explicit `Create tag "..."` actions; new typed tags are normalized and created on save if missing
- local dropdown option sets are immediately updated with newly typed selections so users can re-select without waiting for a backend refetch
- frontend install/build commands are unchanged:
  - install: `npm install`
  - test: `npm run test`
  - build: `npm run build`
- graph rendering now uses `reactflow` dependency for pan/zoom/layouted group visualization
- groups workspace summary rail is viewport-bounded on wide screens and uses internal scrolling to avoid long-page growth for large group counts
- scrollbar width jitter is reduced across route switches and entry editor popup open/edit states by reserving gutter space

## Constraints / Known Limitations

- no pagination controls in agent thread/timeline UI yet
- entry edit-before-approve in the review modal still uses raw JSON override (no structured form editor yet)
- legacy delete proposals created before CRUD-aware rendering may still include verbose `impact_preview` payload context from historical runs
- `Approve & Next` intentionally looks for the next pending item after current index only; if remaining pending items are above, reviewers must scroll back
- `Approve All` is implemented as sequential per-item API calls (no batch endpoint), so very large runs may feel slower
- popup auto-save requires valid required fields; invalid dirty state keeps popup open and surfaces validation errors
- entry property wrappers are non-label containers so only direct control clicks activate inputs/selects
- streaming bubble renders plain text deltas during SSE; markdown formatting is applied after the final assistant message is persisted/refetched
- composer paste/drag-drop paths accept image and PDF files; unsupported file types are skipped with a local error message
- bundle output can still report large chunk warnings because `EntryEditorModal`/BlockNote and charting bundles are heavy even after route-level lazy loading
- taxonomy UI is flat-list only in V1:
  - no delete flow for category terms
  - no parent-term hierarchy editing
