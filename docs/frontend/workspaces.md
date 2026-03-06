# Frontend Workspaces

## Entries

### `frontend/src/pages/EntriesPage.tsx`

- lists, filters, edits, and deletes entries
- create action is a compact `+` beside the `Source text` filter
- `Tag` and `Currency` filters use chip-based multi-select controls
- group column hides UUID-only unnamed groups
- date column is fixed-width and no-wrap
- name cells show the primary name plus a compact `from -> to` secondary line
- rows show a `Missing entity` badge when preserved labels remain after entity or account deletion
- entry create modal resolves default currency from runtime settings

### `frontend/src/pages/EntryDetailPage.tsx`

- shows entry detail plus linked-group graph
- link create and delete use the shared `LinkEditorModal`
- source and target entry pickers use searchable `SingleSelect`
- editing uses the shared popup editor and the same runtime-settings defaults as create flow
- detail cards show `Missing entity` badges when preserved `from` or `to` labels no longer have linked entity records

## Groups

### `frontend/src/pages/GroupsPage.tsx`

- dedicated derived-group workspace at `/groups`
- left summary list comes from `GET /groups`
- selected graph detail comes from `GET /groups/{group_id}`
- group topology changes remain link-driven only
- `GroupGraphView.tsx` locally filters React Flow warning `002` because it is a false positive for this graph

## Accounts

### `frontend/src/pages/AccountsPage.tsx`

- page is a thin orchestrator; domain state lives in `frontend/src/features/accounts/useAccountsPageModel.ts`
- UI is split into `AccountsTableSection`, `ReconciliationSection`, `SnapshotsSection`, and `AccountDialogs`
- create, edit, and delete flows are dialog-driven
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
- taxonomy term tables expose `Entity Categories` and `Tag Types`
- account-backed entities are hidden from the generic `Entities` table
- entities and tags have destructive confirmation dialogs
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

- categorized runtime settings workspace with `General`, `Agent Runtime`, and `Reliability` sections
- supports save/update and reset-to-server-default flows
- settings changes invalidate dependent query surfaces
- `Agent memory` is persisted and sent to every backend agent system prompt
