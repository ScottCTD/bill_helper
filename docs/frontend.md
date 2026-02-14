# Frontend Documentation

## Stack

- React 19
- TypeScript
- Vite
- React Router
- TanStack Query
- Recharts
- Tailwind CSS
- `shadcn/ui` component primitives
- Radix UI primitives (Dialog/Select/Checkbox/Label/Slot)

## Build and Runtime

- Dev server: `npm run dev` (default `http://localhost:5173`)
- Production build: `npm run build`
- API base override: `VITE_API_BASE_URL` (optional)

## App Shell and Routing

Defined in `frontend/src/App.tsx`.

Current shell behavior:

- tokenized top app bar with route actions (`Home`, `Dashboard`, `Entries`, `Accounts`, `Properties`, `Settings`)
- content canvas is route-driven (no global right-side agent occupancy on non-home pages)
- home route is AI-native and renders the agent experience as the primary page content
- outer route wrapper card removed so page sections are visually separated instead of nested in a single container
- readable container width tuned for full-page content
- responsive behavior:
  - home agent page uses full-width content area
  - reusable drawer styling is still supported by `AgentPanel` for optional future use

Pages:

- `/` -> AI home chat
- `/dashboard` -> dashboard analytics
- `/entries` -> entry list
- `/entries/:entryId` -> entry detail
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

## `frontend/src/lib/queryKeys.ts`

Responsibilities:

- centralized TanStack Query key factory by domain
- stable key shapes for list/detail/thread/account-derived queries
- avoids ad-hoc string arrays across pages/components
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
- `getAgentThread`
- `sendAgentMessage`
- `getAgentRun`
- `approveAgentChangeItem`
- `rejectAgentChangeItem`

## Page/Container Responsibilities

## `EntriesPage.tsx`

- list/filter entries
- open unified entry popup for create/edit via row double-click
- delete entry
- creation action is a compact `+` button placed beside the `Source text` filter
- no separate top entry-creation card
- group column only renders explicit group names; UUID-only unnamed groups are hidden
- table row density is compacted and delete action is de-emphasized
- popup property rows use compact inline `Label: control` formatting for tighter scanability
- `Kind / Amount / Currency` and `From / To` rows are tuned to remain single-line in desktop popup width
- `Owner` row is constrained to single-line in desktop popup width
- `Status` has been removed from entry create/edit/list/filter UI and from entry payloads
- entry create modal default currency now resolves from runtime settings (`GET /settings`)
- `Kind` table cell uses symbol-only indicators (`+` for income, `-` for expense)
- amount cells now render with ISO code prefix (for example `CAD 8.13`)
- now uses shared shadcn primitives for card layout, filters, badges, and table actions
- filter toolbar now uses shared table-shell classes aligned with `Properties`:
  - `.table-toolbar`
  - `.table-toolbar-filters`
  - `.table-toolbar-action`

## `EntryDetailPage.tsx`

- entry details and group graph
- link create/delete
- uses shared popup editor for edits (same auto-save behavior as entries list popup)
- now uses shared shadcn primitives for cards, action buttons, and link form controls
- editor wiring also consumes runtime settings defaults for consistency with create flow

## `AccountsPage.tsx`

- account CRUD updates
- snapshot create/list
- reconciliation display
- create-account default currency now resolves from runtime settings (`GET /settings`)

## `PropertiesPage.tsx`

- two-level information architecture:
  - `Core`: Users, Entities, Tags, Currencies
  - `Taxonomies`: Entity Categories, Tag Categories
- left rail section switching (stacks into wrapped segmented groups on smaller screens)
- one active table surface at a time instead of one long vertical section wall
- shared table shell per section:
  - title/subtitle row
  - unified filter toolbar
  - compact right-aligned `+` add action for editable sections
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
  - `Agent Runtime` (API key override, base URL, model, step/image limits)
  - `Reliability` (retry policy controls)
- top summary surface shows effective API key source and active model
- supports save/update and reset-to-server-default flows
- setting changes trigger cache invalidation across dependent pages (agent/dashboard/accounts/entries/users)

## Agent UI

## `frontend/src/components/agent/AgentPanel.tsx`

Used as the primary AI page (`/`) via `frontend/src/pages/HomePage.tsx`.

Timeline features:

- left conversation history rail (thread list) with compact one-line thread buttons
- thread label uses the first 20 characters of the thread title (thread titles are seeded from the first user message)
- click-to-open conversation behavior from history rail
- header title includes active model context (`Agent (<model>)`) based on the most recent run in the selected thread
- main chat timeline with user/assistant message bubbles
- assistant/system message bodies render markdown via `react-markdown` + `remark-gfm` (sanitized defaults, GFM tables/task lists/strikethrough)
- attachment previews for uploaded images
- run blocks are anchored to assistant-side timeline events (`assistant_message_id`) to keep tool activity in assistant flow
- active runs without an assistant message render as temporary assistant-side working blocks
- pending working blocks no longer render an extra trailing helper sentence below tool activity
- tool-call trace panels are collapsible by default with summary rows (tool name, status, timestamp)
- expanded tool-call details show input/output JSON payloads in scrollable blocks
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
  - structured unified diff lines rendered from payload JSON
  - additive `+` lines for proposal payload snapshots
  - paired `-`/`+` lines when reviewer-edited entry JSON differs from the original payload
  - supports labeled proposal blocks for entry/tag/entity create/update/delete types
  - entry create proposals support edit-before-approve via JSON override textarea
- sticky action bar:
  - `Reject` (focused pending item)
  - `Approve` (focused pending item)
  - `Approve & Next` (focused item, then smooth-scroll/focus next pending item after current index)
  - `Approve All` (sequentially applies all pending items in deterministic order, continues through failures)
  - pending context text (`Pending X of Y`) and focused ordinal
- apply-failure handling:
  - failures are surfaced inline on proposal blocks
  - `Approve All` shows `Applied X / Failed Y` summary with quick-jump links to failed items

Composer:

- text area
- multi-image upload input
- compact removable image icon chips above the composer (thumbnail + extra-small corner remove button that does not obscure preview)
- click-to-preview image dialog before send
- `Cmd+Enter` (or `Ctrl+Enter`) submits the composer form
- paste image attachments directly into the composer (`Cmd/Ctrl+V`)
- drag-and-drop image files onto the composer drop target
- optimistic user message rendering: user bubble appears immediately after submit, before run completion
- one-click send
- assistant response streaming playback in the chat timeline (token-by-token render effect)
- explicit "working..." placeholder while message run is pending
- active-run polling refreshes timeline state while backend run status is `running`

Layout modes:

- `mode="page"` for full-page AI home experience
- `mode="drawer"` for optional overlay/drawer presentation

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
- `GroupGraphView.tsx`
- `MetricCard.tsx`
- `ui/MarkdownRenderer.tsx`
- `agent/review/AgentRunReviewModal.tsx`
- `agent/review/diff.ts`
- `components/ui/*` (new shadcn-based primitive layer)
  - `button.tsx`, `card.tsx`, `dialog.tsx`, `input.tsx`, `textarea.tsx`, `badge.tsx`, `table.tsx`, `select.tsx`, `checkbox.tsx`, `label.tsx`, `separator.tsx`, `native-select.tsx`
  - `NativeSelect` now supports wrapper-level sizing via `wrapperClassName` so narrow controls keep caret alignment

## Styling (`frontend/src/styles.css`)

Includes:

- Tailwind base/components/utilities imports
- CSS variable token layer (`--background`, `--foreground`, `--primary`, `--border`, `--ring`, `--success`, etc.)
  - base app background/surfaces now default to white with restrained neutral accents
- global UI typography uses a product-style sans stack (`Inter` -> SF Pro -> Segoe UI/Roboto fallbacks) instead of editorial/body-copy-first styling
- component classes for legacy/transitioned surfaces (`.card`, `.form-grid`, `.field`, `.agent-panel`, `.tag-multiselect`, editor/chart helpers)
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
  - collapsible tool-call details
  - draft attachment chip + preview dialog styling
  - cumulative thread usage/cost bar styling above composer
- button baseline behavior is scoped to unclassed legacy buttons so `shadcn/ui` variant buttons are not overridden
- spacing scale was relaxed (`app-content`, `stack`, `grid`, form gaps) to reduce crowded coupling between sections
- account picker controls now use consistent rounded chip geometry and focus/hover/selected states (no square text-only selected boxes)
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

- frontend now depends on agent API contracts and attachment URLs
- multipart requests are required for agent message send with images
- all query keys/invalidation rules are now centralized, so new pages/features should reuse `queryKeys` + `queryInvalidation` helpers
- UI primitives should be sourced from `frontend/src/components/ui/*` before introducing one-off controls/styles
- properties page now issues taxonomy reads in addition to users/entities/tags/currencies:
  - `GET /taxonomies`
  - `GET /taxonomies/entity_category/terms`
  - `GET /taxonomies/tag_category/terms`
- taxonomy term create/rename and entity/tag category assignment changes now invalidate taxonomy-term usage caches
- entry popup save flow is now close-driven:
  - clicking outside/closing attempts to auto-save when there are changes
  - clean/no-change close exits immediately without write calls
- entry popup no longer sends `account_id` in create/edit payloads; `From`/`To` entity fields are the primary relation inputs
- `From`/`To` fields now accept typed values with entity suggestions:
  - exact match to existing entity name -> sends `from_entity_id` / `to_entity_id`
  - non-matching typed name -> sends `from_entity` / `to_entity` so backend creates the entity
  - non-empty typed values always render an explicit `Create "..."` option in the entity dropdown
  - created entity options are shared across both `From` and `To` dropdowns during the current edit session
- `Tags` input remains creatable; new typed tags are normalized and created on save if missing
- local dropdown option sets are immediately updated with newly typed selections so users can re-select without waiting for a backend refetch
- frontend install/build commands are unchanged:
  - install: `npm install`
  - build: `npm run build`
- scrollbar width jitter is reduced across route switches and entry editor popup open/edit states by reserving gutter space

## Constraints / Known Limitations

- no pagination controls in agent thread/timeline UI yet
- entry edit-before-approve in the review modal still uses raw JSON override (no structured form editor yet)
- `Approve & Next` intentionally looks for the next pending item after current index only; if remaining pending items are above, reviewers must scroll back
- `Approve All` is implemented as sequential per-item API calls (no batch endpoint), so very large runs may feel slower
- popup auto-save requires valid required fields; invalid dirty state keeps popup open and surfaces validation errors
- entry property wrappers are non-label containers so only direct control clicks activate inputs/selects
- current streaming UI is client-rendered from the completed assistant message; runs are polled until completion but backend SSE/token streaming endpoint is not implemented yet
- composer paste/drag-drop paths accept only image files; non-image files are skipped with a local error message
- bundle output still reports large chunk warnings from existing editor/runtime bundles; this refactor did not add route-level code splitting
- taxonomy UI is flat-list only in V1:
  - no delete flow for category terms
  - no parent-term hierarchy editing
