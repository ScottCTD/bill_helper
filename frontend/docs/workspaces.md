# Frontend Workspaces

## Entries

### `frontend/src/pages/EntriesPage.tsx`

- lists, filters, edits, and deletes entries
- create action is a compact `+` beside the `Source text` filter
- `Tag` and `Currency` filters use chip-based multi-select controls
- date column is fixed-width and no-wrap
- name cells show the primary name plus a compact `from -> to` secondary line
- amount cells combine the kind marker with the numeric value, reusing the existing `+ / - / ~` tone colors on the symbol itself with tight inline spacing
- tag cells render colored chips using configured tag colors or the shared deterministic fallback color
- the name and tags columns use balanced preferred widths so tags can expand when there is room, while still yielding space before the name column on tighter layouts
- row delete actions use compact trash-can icon buttons with accessible labels instead of inline `Delete` text, and their icon-only action headers are visually hidden to keep the column minimal
- rows show a `Missing entity` badge when preserved labels remain after entity or account deletion
- entry create modal resolves default currency from runtime settings
- entry create/edit modal includes a single direct-group picker; `SPLIT` groups also show a split-role picker
- entry create/edit modal treats re-selecting a same-name existing entity as a real relink, so preserved missing labels can be restored without renaming the field

### `frontend/src/pages/EntryDetailPage.tsx`

- shows entry detail, direct-group context, and the direct-group graph when the entry is assigned
- uses `direct_group` and `group_path` from `GET /entries/{entry_id}` instead of rendering raw link rows
- popup editing includes the same direct-group and split-role controls as the entries page modal
- routes structural edits into the groups workspace via a dedicated `Open groups workspace` action
- editing uses the shared popup editor and the same runtime-settings defaults as create flow
- detail cards show `Missing entity` badges when preserved `from` or `to` labels no longer have linked entity records

## Groups

### `frontend/src/pages/GroupsPage.tsx`

- dedicated first-class group workspace at `/groups`
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
- UI is split into `AccountsTableSection`, `ReconciliationSection`, `SnapshotsSection`, and `AccountDialogs`
- create, edit, and delete flows are dialog-driven
- account rows single-select on click and open edit on double-click; delete remains the only explicit row action and is rendered as a compact icon button
- account ids are shared entity-root ids; generic entity management does not expose them as editable entity rows
- account dialogs edit `Owner`, `Name`, `Currency`, `Notes`, and `Active`
- legacy `institution` and `type` fields are removed
- reconciliation and snapshot side panels are driven by the selected table row
- delete confirmation warns that snapshots are removed and preserved entry labels will surface missing-entity markers

## Properties

### `frontend/src/pages/PropertiesPage.tsx`

- page is a thin orchestrator over `frontend/src/features/properties/*`
- section navigation and content rendering are split into dedicated components
- section state, form state, queries, and filtered data live in focused hooks
- editable sections use modal-driven create and edit flows
- users, entities, and tags open edit modals on row double-click instead of explicit row Edit buttons
- taxonomy term tables expose `Entity Categories` and `Tag Types`
- account-backed entities are hidden from the generic `Entities` table
- the generic `Entities` table now stays compact and shows only `Name`, `Category`, and row actions
- entities and tags have destructive confirmation dialogs
- account, entity, and tag row delete controls use compact icon buttons with subdued shared table action styling; destructive emphasis is reserved for confirmation
- entity delete warns when preserved entry labels will become missing markers
- tag delete warns when existing entry-tag associations will be removed
- currencies remain read-only

## Dashboard

### `frontend/src/pages/DashboardPage.tsx`

- tabbed analytics surface with `Overview`, `Daily Spend`, `Breakdowns`, and `Insights`
- uses Recharts with measured containers so charts render only after non-zero dimensions are available
- dashboard totals and charts exclude internal transfers when both endpoints resolve to account-backed entity roots
- daily classification uses `daily` vs `non-daily` tags

## Settings

### `frontend/src/pages/SettingsPage.tsx`

- thin route shell over `frontend/src/features/settings/*`
- tabbed runtime settings workspace with `General` and `Agent` tabs, each rendering focused section cards
- uses a compact sticky top toolbar as the first page element, including the `Settings` title, section tabs, save action, and reset-to-server-default from a dedicated `General` tab reset section
- settings changes invalidate dependent query surfaces
- query, mutation, and form orchestration live in `frontend/src/features/settings/useSettingsPageModel.ts`
- reusable runtime-settings parsing and payload validation live in `frontend/src/features/settings/formState.ts`
- `General` groups read-only identity context separately from ledger default currencies
- `Agent` groups memory/models, provider overrides, run limits, bulk and attachment limits, and reliability into separate sections
- section UI is split across `SettingsToolbar.tsx`, `SettingsGeneralSection.tsx`, `SettingsAgentSection.tsx`, and `ResetSettingsDialog.tsx`
- `Agent memory` lives under the `Agent` tab, is edited as one item per line, persists as a list of strings, and is sent to every backend agent system prompt
- `Default model` is edited separately from `Available models`; available models use one newline-separated identifier per line and preserve entered order
- bulk concurrency is labeled around concurrent launches, while the per-message attachment limit explicitly calls out that Bulk mode still starts one fresh thread per attachment
- agent provider overrides use a compact toggle; when off the custom endpoint/key fields are hidden and saving falls back to server env values from `.env` or process env
