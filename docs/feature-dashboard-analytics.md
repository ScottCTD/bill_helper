# Feature Map: Dashboard Analytics

This doc is the fast path for understanding dashboard metrics, data boundaries, and chart mapping.

## Scope

- `GET /api/v1/dashboard`
- dashboard-specific backend aggregations
- frontend dashboard tabs/charts

## Data Boundary Rules

- Dashboard analytics currently use `CAD` only.
- Entries in other currencies are excluded from dashboard calculations.
- Reconciliation panel includes active CAD accounts only.

## Daily vs Non-daily Classification

For expense entries:

- `daily` tag => daily spending
- `non-daily` / `non_daily` / `nondaily` => non-daily (override)
- no daily tag => non-daily

Classification logic lives in `backend/services/finance.py`.

## Backend Flow

1. `backend/routers/dashboard.py` parses `month`.
2. `backend/services/finance.py` computes:
   - `kpis`
   - `daily_spending`
   - `monthly_trend`
   - `spending_by_from`, `spending_by_to`, `spending_by_tag`
   - `weekday_spending`
   - `largest_expenses`
   - `projection`
3. Router returns `DashboardRead` from `backend/schemas.py`.

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

- `backend/tests/test_finance.py` validates dashboard payload shape and key metrics.

## Operational Notes

- Projection fields are null for non-current months.
- Frontend amount display is code-prefixed (`CAD 8.13`) via `frontend/src/lib/format.ts`.
- Dashboard charts stay blank until the first card measurement completes; after that, chart resizing is driven by the measured card container.
