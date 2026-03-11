# Dashboard And Entries

## Dashboard

- the dashboard loads month availability from `GET /dashboard/timeline`, then loads the selected month from `GET /dashboard?month=...`
- month chips are driven by the timeline payload, not by local date math
- the dashboard surface includes:
  - summary hero cards for spend and net totals
  - filter-group chips using `dashboard.filter_groups`
  - daily spending and monthly trend charts
  - largest-expense cards
  - reconciliation summary rows for tracked accounts
- empty state is driven by the returned dashboard payload rather than a transport-only heuristic

## Entries

- the entries tab loads the ledger list plus editor resources for tags, groups, entities, users, currencies, and filter groups
- the main list supports native search plus local filters for:
  - kind
  - tag
  - currency
  - source text
  - filter group
- rows support swipe edit and swipe delete actions
- detail screens fetch canonical entry detail with `GET /entries/{id}`

## Entry Editor

- create and edit both use a native `Form` sheet
- the editor supports direct-group assignment and only shows split-role selection when the selected group is a `SPLIT`
- client-side validation blocks invalid direct-group role combinations before the request is sent
- successful create, update, and delete operations refetch the canonical list state

## Files

- `ios/BillHelperFeatures/Sources/DashboardEntriesFeatures.swift`
- `ios/BillHelperCore/Sources/APIClient+Finance.swift`
- `ios/BillHelperCore/Sources/FinanceDashboardModels.swift`
- `ios/BillHelperCore/Sources/FinanceLedgerModels.swift`
