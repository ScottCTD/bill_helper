# Frontend Workspaces

# Shared Page Chrome

- the main ledger workspaces now share the same page vocabulary:
  - `PageHeader` for the route-level title and summary
  - `WorkspaceSection` for the primary table/form surface
  - `WorkspaceToolbar` for filters, search, and compact actions
  - `StatBlock` for dense metric summaries where a card grid would be too decorative
- the shared app scroll container reserves vertical scrollbar gutter space even when a page does not overflow, so route-level content edges stay aligned across pages like `Agent`, `Filters`, and `Entries`; the route scrollbar thumb stays visually hidden at rest and only appears during active page scrolling
- settings remains the exception in structure because its sticky toolbar is still the primary page header pattern

## Entries

### `frontend/src/pages/EntriesPage.tsx`

- lists, filters, edits, and deletes entries
- route shell now uses the shared page header plus one primary workspace section instead of wrapping the title in a card
- create action is a compact `+` beside the `Source text` filter
- `Tag` and `Currency` filters use chip-based multi-select controls whose menus float above the workspace card instead of being clipped by empty or short table states
- a `Filter group` selector syncs with the `filter_group_id` URL search param so deep links can open the entries list already scoped to one saved group
- entry rows are loaded incrementally in backend-sized pages; reaching the bottom of the table auto-loads the next slice and a fallback `Load more` button remains visible while more rows exist
- date column is fixed-width and no-wrap
- name cells show the primary name plus a compact `from -> to` secondary line
- amount cells combine the kind marker with the numeric value, reusing the existing `+ / - / ~` tone colors on the symbol itself with tight inline spacing
- tag cells render colored chips using configured tag colors or the shared deterministic fallback color
- the name and tags columns use balanced preferred widths so tags can expand when there is room, while still yielding space before the name column on tighter layouts
- row delete actions use compact trash-can icon buttons with accessible labels instead of inline `Delete` text, and their icon-only action headers are visually hidden to keep the column minimal
- rows show a `Missing entity` badge when preserved labels remain after entity or account deletion
- entry create modal resolves default currency from runtime settings
- entry create/edit modal includes a single direct-group picker; `SPLIT` groups also show a split-role picker
- entry create/edit modal keeps the markdown notes editor inside the shared field grid with a labeled `Notes` row instead of a detached full-width block
- entry create/edit modal includes a compact swap icon control between the `from` and `to` selectors to swap both field values in one click
- entry create/edit modal tag picking supports fuzzy search and ranks the strongest matches first before falling back to create-new
- entry create/edit modal treats re-selecting a same-name existing entity as a real relink, so preserved missing labels can be restored without renaming the field
- entry create/edit modal does not expose owner controls; submitted entries stay bound to the authenticated user's current scope
- entry create/edit modal adds an inline AI tag-suggestion button beside the tag picker; it uses the current draft plus similar tagged entries, replaces the current modal tag selection on success, and aborts cleanly on second click or modal close without entering the agent workspace/history

### `frontend/src/pages/EntryDetailPage.tsx`

- shows entry detail, direct-group context, and the direct-group graph when the entry is assigned
- uses `direct_group` and `group_path` from `GET /entries/{entry_id}` instead of rendering raw link rows
- popup editing includes the same direct-group and split-role controls as the entries page modal
- routes structural edits into the groups workspace via a dedicated `Open groups workspace` action
- editing uses the shared popup editor and the same runtime-settings defaults as create flow
- detail cards show `Missing entity` badges when preserved `from` or `to` labels no longer have linked entity records

## Entities

### `frontend/src/pages/EntitiesPage.tsx`

- dedicated first-class entity workspace at `/entities`
- page is a thin orchestrator over `frontend/src/features/entities/*`
- route shell now uses the shared page header plus one primary workspace section
- generic entity management stays focused on non-account counterparties; account-backed entity roots remain managed from `Accounts`
- table shows `Name`, `Category`, a net-money aggregate column, and icon-only row actions
- rows open the edit dialog on double-click and keep delete isolated behind the compact trash action
- create and edit dialogs reuse entity-category taxonomy terms plus existing category values as suggestions
- net-money values only render as an amount when the entity's visible entries share one currency; mixed-currency entities show a fallback label instead of a misleading sum
- delete confirmation warns when preserved entry labels will show a missing-entity marker

## Groups

### `frontend/src/pages/GroupsPage.tsx`

- dedicated first-class group workspace at `/groups`
- route shell now uses the shared page header plus one primary workspace section
- organized around a broad searchable groups table first, with each row opening a dedicated group-detail modal on double-click and a fallback `View` action
- browser table data comes from `GET /groups`
- group detail modal content comes from `GET /groups/{group_id}`
- supports create, rename, delete, add-entry, add-child-group, and remove-member flows
- child-group picking is limited to top-level groups that are not already attached elsewhere, matching the depth-1/no-sharing backend rules
- group detail modal surfaces compact direct-entry stats above the member table and keeps the derived graph at the bottom of the modal
- direct members table inside the modal shows both entries and child groups, exposes entry amounts in the same signed compact format as the entries table, and lets a member click open the corresponding entry editor or child-group detail
- `GroupGraphView.tsx` renders both entry nodes and child-group nodes, with layout rules per `group_type`
- `GroupGraphView.tsx` locally filters React Flow warning `002` because it is a false positive for this graph

## Accounts

### `frontend/src/pages/AccountsPage.tsx`

- page is a thin orchestrator; domain state lives in `frontend/src/features/accounts/useAccountsPageModel.ts`
- route shell now uses the shared page header plus one primary workspace section
- UI is split into `AccountsTableSection`, `ReconciliationSection`, `SnapshotHistoryTable`, `SnapshotCreatePanel`, and `AccountDialogs`
- create, edit, and delete flows are dialog-driven
- account rows single-select on click and open edit on double-click; delete remains the only explicit row action and is rendered as a compact icon button
- account ids are shared entity-root ids; generic entity management does not expose them as editable entity rows
- account creation edits `Name`, `Currency`, and `Notes`; owner is implicit from the authenticated user's current scope
- the account edit modal is untabbed and fixed-height: a compact top details form (`Name`, `Currency`, `Active`, `Notes`) sits above a two-column lower workspace
- the lower workspace keeps reconciliation and snapshot history in the left internal scroll column, with snapshot creation isolated in a compact right-side panel
- legacy `institution` and `type` fields are removed
- reconciliation and snapshot history inside the edit modal are driven by the selected row that opened it
- snapshot history rows expose per-snapshot delete actions with confirmation
- delete confirmation warns that snapshots are removed and preserved entry labels will surface missing-entity markers

## Properties

### `frontend/src/pages/PropertiesPage.tsx`

- page is a thin orchestrator over `frontend/src/features/properties/*`
- route shell now uses the shared page header plus one primary workspace section
- section navigation and content rendering are split into dedicated components
- section state, form state, queries, and filtered data live in focused hooks
- editable sections use modal-driven create and edit flows
- editable sections now cover tags plus taxonomy term tables; user CRUD moved to `/admin`
- taxonomy term tables expose `Entity Categories` and `Tag Types`
- tags have destructive confirmation dialogs
- tag row delete controls use compact icon buttons with subdued shared table action styling; destructive emphasis is reserved for confirmation
- tag delete warns when existing entry-tag associations will be removed
- currencies remain read-only

## Auth And Admin

### `frontend/src/pages/LoginPage.tsx`

- password-only sign-in surface
- stores the opaque session token in `bill-helper.session-token`
- redirects back to the originally requested protected route after success

### `frontend/src/pages/AdminPage.tsx`

- admin-only workspace for user and session management
- supports create, rename, role changes, password reset, delete, and `Log in as`
- session table can revoke bearer tokens without deleting the owning user

## Dashboard

### `frontend/src/pages/DashboardPage.tsx`

- tabbed analytics surface with `Overview`, `Spending`, `Breakdowns`, and `Insights`
- route shell now uses the shared page header, a shared control surface, and `StatBlock` summaries instead of bespoke metric cards for the top-line KPIs
- includes an explicit `Month` / `Year` mode toggle
- uses a dedicated right-side timeline rail on wide screens for month/year selection, with centered snap-scrolling so the active month or year stays visually anchored
- desktop wheel interaction is discrete: one wheel gesture advances one visible month or year with a smooth centered transition, and only expense-bearing months/years appear in the rail
- on small screens the timeline falls back to a compact horizontal strip above the dashboard content
- yearly mode moves annual trend charts into the active dashboard view instead of hiding them only inside `Insights`
- uses Recharts with measured containers so charts render only after non-zero dimensions are available
- dashboard totals and charts exclude internal transfers when both endpoints resolve to account-backed entity roots
- monthly classification is driven by saved filter groups, including yearly views that fan out to month-scoped dashboard reads for the selected and previous years
- the monthly and yearly `Income vs Expense Trend` charts render income as a standalone bar and expense as stacked filter-group segments using a restrained dashboard-specific palette rather than raw saved filter-group colors
- `Insights` is intentionally reduced to the largest-expenses table only; month mode shows the current month while year mode aggregates the selected year's largest expenses

## Filters

### `frontend/src/pages/FilterGroupsPage.tsx`

- dedicated first-class filter-group workspace at `/filters`
- route shell now uses the shared page header plus one primary workspace section
- page shell delegates the actual CRUD surface to `frontend/src/features/filterGroups/FilterGroupsManager.tsx`
- the workspace now uses a master-detail layout: a selectable filter-group list on the left and one focused editor on the right, with the list stacking above the editor on small screens
- the primary `Create group` / `Save changes` action now sits in the route-level page header and reflects the currently selected editor session
- the primary editor hides the raw backend `rule_summary` prose and instead uses a guided include/exclude rule builder with literal `AND` / `OR` controls
- the built-in `untagged` group is a computed system bucket and opens as a read-only detail panel instead of the normal editor
- tag-based conditions use the shared `TagMultiSelect` component with the existing tag catalog instead of a comma-separated text field
- nested rule groups still work, but they are moved behind an `Advanced` mode that opens automatically for already-nested rules
- each saved group exposes a direct `View matching entries` link that opens the entries workspace scoped to that group

## Workspace

### `frontend/src/pages/WorkspacePage.tsx`

- dedicated current-user workspace page at `/workspace`
- route is IDE-first and strips away extra page chrome: when the workspace is healthy, the page is just the embedded `code-server` iframe rather than a tree-first CRUD layout
- the workspace shell stays mounted under the authenticated app chrome, so switching from `/workspace` to another in-app route and back reuses the same iframe instead of remounting `code-server`
- the IDE opens the `/workspace` volume root, which now contains two user-facing top-level folders: `scratch/` for writable working files and `uploads/` for the direct read-only canonical upload tree
- the workspace image ships with the web-compatible `chocolatedesue.modern-pdf-preview` extension preinstalled so PDFs in `uploads/` open inside the browser IDE instead of falling back to binary text
- the embedded `code-server` runtime writes default user settings that disable built-in VS Code AI surfaces, suppress the welcome page on launch, trust the opened folder by default, move the workbench side bar to the right to avoid fighting the app-level nav on the left, and open PDFs in single-page mode by default
- on entry, the page calls `POST /workspace/ide/session` to start the workspace if needed, mint the narrow workspace cookie, and load the proxied IDE
- while the IDE session or iframe is still starting, the stage shows a centered loading spinner instead of static copy cards
- degraded or narrow/mobile states now use one minimal fallback card only; the old in-app file-tree/details surface was removed instead of being kept as a compatibility panel
- narrow/mobile viewports do not embed the IDE; they show a desktop-first message only

## Settings

### `frontend/src/pages/SettingsPage.tsx`

- thin route shell over `frontend/src/features/settings/*`
- tabbed runtime settings workspace with `General` and `Agent` tabs, each rendering focused section cards
- uses a compact sticky top toolbar as the first page element, including the `Settings` title, section tabs, save action, and reset-to-server-default from a dedicated `General` tab reset section
- settings changes invalidate dependent query surfaces
- query, mutation, and form orchestration live in `frontend/src/features/settings/useSettingsPageModel.ts`
- reusable runtime-settings parsing and payload validation live in `frontend/src/features/settings/formState.ts`
- `General` groups ledger default currencies and the reset-to-server-default action
- `Agent` groups memory/models, provider overrides, run limits, bulk and attachment limits, and reliability into separate sections
- section UI is split across `SettingsToolbar.tsx`, `SettingsGeneralSection.tsx`, `SettingsAgentSection.tsx`, and `ResetSettingsDialog.tsx`
- `Agent memory` lives under the `Agent` tab, is edited as one item per line, persists as a list of strings, and is sent to every backend agent system prompt
- `Default model` is chosen from a dropdown sourced from `Available models`; available models still use one newline-separated identifier per line, preserve entered order, and fallback the default to the first remaining listed model if the current selection is removed
- `Default tagging model` is a separate optional dropdown sourced from `Available models`; leaving it blank disables inline entry tag suggestion, and removing the selected model from `Available models` auto-clears it back to blank
- bulk concurrency is labeled around concurrent launches, while the per-message attachment limit explicitly calls out that Bulk mode still starts one fresh thread per attachment
- agent provider overrides use a compact toggle; when off the custom endpoint/key fields are hidden and saving falls back to server env values from `.env` or process env
