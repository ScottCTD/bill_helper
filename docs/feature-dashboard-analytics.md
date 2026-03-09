# Feature Map: Dashboard Analytics

This doc is the fast path for understanding dashboard metrics, data boundaries, and chart mapping.

## Scope

- `GET /api/v1/dashboard`
- dashboard-specific backend aggregations
- frontend dashboard tabs/charts

## Data Boundary Rules

- Dashboard analytics currently use `CAD` only.
- Entries in other currencies are excluded from dashboard calculations.
- Entries whose `from_entity_id` and `to_entity_id` both resolve to account-backed entity roots (`accounts.id` membership) are treated as internal transfers and excluded from dashboard KPIs, trends, breakdowns, largest-expense ranking, and projection math.
- Reconciliation panel includes active CAD accounts only.

## Daily vs Non-daily Classification

For expense entries:

- `daily` tag => daily spending
- `non-daily` / `non_daily` / `nondaily` => non-daily (override)
- no daily tag => non-daily

Classification logic lives in `backend/services/finance.py`.

## Backend Flow

1. `backend/routers/dashboard.py` validates the `month` format and delegates to `backend/services/finance.py`.
2. `backend/services/finance.py` resolves dashboard currency/runtime settings, computes:
   - `kpis`
   - `daily_spending`
   - `monthly_trend`
   - `spending_by_from`, `spending_by_to`, `spending_by_tag`
   - `weekday_spending`
   - `largest_expenses`
   - `projection`
3. The same service module loads principal-scoped reconciliation accounts and returns `DashboardRead` from `backend/schemas_finance.py`.

## Frontend Mapping

`frontend/src/pages/DashboardPage.tsx`:

- `Overview` tab:
  - KPI cards
  - income vs expense trend
  - daily vs non-daily split
  - projection cards
- `Daily Spend` tab:
  - average/median daily metrics
  - daily area chart
  - monthly daily vs non-daily bars
- `Breakdowns` tab:
  - tag pie
  - destination/source bar charts
- `Insights` tab:
  - weekday distribution
  - largest expenses table
  - reconciliation table

Interactive charting is powered by Recharts.
`frontend/src/pages/DashboardPage.tsx` measures each chart card before mounting the chart itself, which avoids the dev-time `-1 x -1` container warnings that Recharts emits when a panel has not completed layout yet.

## Tests

- `backend/tests/test_finance.py` validates dashboard payload shape, key metrics, and exclusion of internal account-to-account transfers.

## Operational Notes

- Projection fields are null for non-current months.
- Frontend amount display is code-prefixed (`CAD 8.13`) via `frontend/src/lib/format.ts`.
- Dashboard charts stay blank until the first card measurement completes; after that, chart resizing is driven by the measured card container.
- Internal-transfer detection uses account subtype membership only; a generic entity categorized as `account` no longer counts as an internal account endpoint.
