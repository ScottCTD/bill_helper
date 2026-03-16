# Feature Map: Dashboard Analytics

This doc is the fast path for understanding dashboard metrics, filter-group classification, and chart mapping.

## Scope

- `GET /api/v1/dashboard`
- `GET /api/v1/dashboard/timeline`
- `GET /api/v1/agent/dashboard`
- `GET/POST/PATCH/DELETE /api/v1/filter-groups`
- dashboard-specific backend aggregations
- frontend dashboard tabs/charts and the first-class filter workspace

## Data Boundary Rules

- Dashboard analytics use the runtime-configured dashboard currency (`/settings.dashboard_currency_code`).
- Entries in other currencies are excluded from dashboard calculations.
- Entries whose `from_entity_id` and `to_entity_id` both resolve to account-backed entity roots (`accounts.id` membership) are treated as internal transfers and excluded from dashboard KPIs, expense charts, breakdowns, largest-expense ranking, and projection math.
- Entries whose `from_entity_id` and `to_entity_id` both resolve to account-backed entity roots (`accounts.id` membership) are treated as internal transfers and excluded from dashboard KPIs, expense charts, breakdowns, largest-expense ranking, and projection math.

## Filter-Group Classification

Dashboard expense analytics are powered by principal-owned saved filter groups.

Built-in groups are lazily provisioned per user on first dashboard or `/filter-groups` read:

- `day_to_day`
- `one_time`
- `fixed`
- `transfers`
- `untagged`

Current rule engine supports:

- `entry_kind is ...`
- `tags has_any [...]`
- `tags has_none [...]`
- `is_internal_transfer is true|false`
- nested `AND` / `OR` groups
- separate `include` and optional `exclude` trees

Default groups other than `untagged` can have their rules edited, but their names stay fixed. The built-in `untagged` group is computed automatically: it includes expense entries with no tags, plus tagged expense entries that match no other saved group, and it stays read-only. Custom groups can overlap with default groups and with each other.

## Backend Flow

1. `backend/routers/dashboard.py` validates the `month` format, exposes both the month payload and a discrete expense-period timeline feed, delegates to `backend/services/finance_dashboard.py`, and commits any lazily-provisioned default filter groups.
2. `backend/services/filter_groups.py` loads or creates the caller's saved filter groups and returns parsed rule definitions.
3. `backend/services/finance_dashboard.py` resolves dashboard currency/runtime settings, computes:
   - overall expense/income/net KPIs
   - filter-group month totals
   - daily expense series by filter group
   - monthly expense trend by filter group
   - from/to/tag breakdowns
   - weekday distribution
   - largest expenses with matching filter-group keys
   - current-month projection plus projected filter-group totals
4. `backend/routers/agent_dashboard.py` exposes a separate principal-scoped agent usage read model backed by `backend/services/agent_dashboard.py`; it filters to terminal runs, derives USD pricing from persisted token counters, and returns KPI cards, time buckets, token slices, model rows, surface rows, and top expensive runs.
5. `backend/routers/filter_groups.py` exposes CRUD for saved filter groups and also commits default provisioning on first read.
6. `backend/routers/entries.py` can apply a saved filter group server-side via `filter_group_id`, so the entries workspace can open the exact matching ledger rows for any group.

## Frontend Mapping

`frontend/src/pages/DashboardPage.tsx`:

- `Overview` tab:
  - explicit `Month` / `Year` mode toggle
  - floating page-level right-side invisible timeline rail on desktop, sized to the viewport height without consuming dashboard layout width
  - timeline only lists months and years that have visible expense activity in the dashboard currency
  - wheel-based discrete month/year stepping with centered active-item picker behavior; mobile collapses back to a compact horizontal strip
  - monthly mode: KPI cards, an `Income vs Expense Trend` bar chart with one income bar plus stacked expense segments by filter group (bottom to top: fixed, transfers, one-time, day-to-day; tooltip shows segment name and amount on hover), expense pie by filter group, and projection cards
  - yearly mode: yearly KPI cards, monthly income vs expense bars for the selected year with stacked filter-group expense segments, yearly filter-group totals, and a dedicated monthly bar chart for each filter group
- `Spending` tab:
  - monthly mode: average/median spend-day metrics, stacked daily area chart by filter group, and month-over-month comparison cards
  - yearly mode: average/median expense-month metrics, stacked monthly filter-group bars for the selected year, and year-over-year comparison cards for each saved filter group
- `Breakdowns` tab:
  - tag pie
  - destination/source bar charts
  - when yearly mode is active, this tab explicitly stays anchored to the selected month
- `Insights` tab:
  - largest expenses table with matching group badges
  - month mode uses the selected month payload
  - year mode aggregates the largest-expense rows across the selected year's month payloads
- `Agent` tab:
  - separate agent spend controls for `7d` / `30d` / `90d` / `all`
  - model and surface toggle filters backed by `GET /api/v1/agent/dashboard`
  - KPI cards for cost, token volume, average spend, cache hit rate, dominant model, and failure rate
  - cost-over-time area chart, input/output token pie, surface comparison bars, model breakdown table, and top expensive-run table
- `frontend/src/pages/FilterGroupsPage.tsx`:
  - first-class `/filters` workspace linked from the left navigation as `Filters`
  - master-detail filter-group workspace with a guided include/exclude editor for the common flat-rule path
  - the primary `Create group` / `Save changes` action lives in the route-level page header instead of the editor footer
  - the built-in `untagged` group renders as a read-only system panel rather than the normal editor
  - nested logic remains available through an `Advanced` mode that opens automatically for already-nested rules
  - tag conditions reuse the shared `TagMultiSelect` instead of a comma-separated text field
  - per-group deep links into `/entries?filter_group_id=...`

Interactive charting is powered by Recharts.
`frontend/src/features/filterGroups/FilterGroupsManager.tsx` coordinates the filter-group workspace, while the focused editor modules under `frontend/src/features/filterGroups/` render the guided and advanced rule editors.

## Tests

- `backend/tests/test_finance.py` validates filter-group provisioning, dashboard payload shape, overlap behavior for custom groups, and exclusion of internal account-to-account transfers.

## Operational Notes

- Projection fields are null for non-current months, but the projection table still lists each saved filter group with `-`.
- Default filter groups are persisted on read so later edits target stable row ids.
- Shares in `dashboard.filter_groups[*].share` are calculated against total monthly expense; overlapping custom groups can make the summed shares exceed `1.0`.
- The yearly dashboard view is assembled on the frontend from repeated month-scoped `GET /api/v1/dashboard` reads for the selected year and its previous year; no separate yearly endpoint exists yet.
- `GET /api/v1/dashboard/timeline` returns the discrete month list that drives the floating picker rail; the frontend derives the visible year list from that month feed.
- Agent usage analytics are range-based rather than month/year-based; the `Agent` tab keeps its own filters and does not reuse the finance timeline rail state for queries.
