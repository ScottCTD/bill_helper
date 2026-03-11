# Dashboard And Entries

## Dashboard

- the dashboard loads month availability from `GET /dashboard/timeline`, then loads the selected month from `GET /dashboard?month=...`
- month chips are driven by the timeline payload, not by local date math, and the selected month auto-centers on load, refresh, and deep-link selection
- the dashboard surface includes:
  - a monthly hero card with spend, income, net, and spend-day metrics
  - a projection section using `dashboard.projection`
  - filter-group chips using `dashboard.filter_groups`
  - an income-vs-expense trend chart with a selected-filter-group overlay
  - a daily spend chart with the selected-filter-group overlay
  - filter-group distribution, destination/source/tag breakdown charts, and weekday pattern bars
  - largest-expense cards scoped to the selected filter group when possible
  - reconciliation account cards that drill into the real account detail screen instead of a placeholder row
- empty state is driven by the returned dashboard payload rather than a transport-only heuristic

## Entries

- the entries tab loads the ledger list plus editor resources for tags, groups, entities, users, currencies, and filter groups
- the main list supports native search plus local filters for:
  - kind
  - multi-tag selection
  - currency
  - source text
  - filter group
- rows support swipe edit and swipe delete actions
- detail screens fetch canonical entry detail with `GET /entries/{id}`

## Entry Editor

- create and edit both use a native `Form` sheet
- the date field uses a native date picker instead of free-form date text
- tags use a searchable multi-select sheet with create-on-new-tag support and lowercase normalization on save
- the editor supports direct-group assignment and only shows split-role selection when the selected group is a `SPLIT`
- client-side validation blocks missing names, invalid amounts, and invalid split-role state before the request is sent
- notes render and save as markdown-capable text
- successful create, update, and delete operations refetch the canonical list state

## Files

- `ios/BillHelperFeatures/Sources/DashboardEntriesFeatures.swift`
- `ios/BillHelperCore/Sources/APIClient+Finance.swift`
- `ios/BillHelperCore/Sources/FinanceDashboardModels.swift`
- `ios/BillHelperCore/Sources/FinanceLedgerModels.swift`
