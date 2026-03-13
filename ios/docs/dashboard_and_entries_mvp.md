# Dashboard and Entries MVP

## Scope

- `BillHelperFeatures/Sources/DashboardEntriesFeatures.swift`
- `BillHelperApp/Sources/AppConfiguration.swift`
- `BillHelperAPITests/DashboardEntriesFeatureTests.swift`

## Dashboard

- loads `GET /dashboard` for the current month when the tab opens
- shows a calm summary card, KPI tiles, top spending breakdown, largest expenses, and account reconciliation snapshot
- uses explicit loading, empty, and error states with retry affordances

## Entries

- loads `GET /entries` when the tab opens
- shows a mobile-first list with amount, counterparty, tags, and date in each row
- supports pull-to-refresh and navigation into a read-only entry detail view built from the loaded row data
- uses explicit loading, empty, and error states with retry affordances

## Notes

- the mobile surfaces intentionally avoid desktop-style chart density in favor of readable cards and grouped lists
- no local backend port was required for this work item because focused verification used injected view-model loaders and simulator build/test runs