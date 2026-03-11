# Manage And Settings

## Manage Tab

The manage tab is a grouped native workspace for backend-backed finance reference data and admin surfaces.

## Sections

- `Accounts`: list, create, edit, delete, snapshot history, snapshot create/delete, and reconciliation detail
- `Entities`: searchable list plus create, edit, and delete
- `Tags`: searchable list plus create, edit, and delete
- `Groups`: list, create, rename, delete, plus member add/remove flows from group detail
- `Filter Groups`: list, create, edit, delete, and recursive include/exclude rule editing
- `Taxonomies`: taxonomy browser with term list and term create/edit forms
- `Currencies`: read-only reference list
- `Users`: list plus create/edit for principal/admin management

## Permissions

- admin-only mutations are hidden or disabled when the current principal is not an admin
- the manage tab still renders for non-admin users, but edit capabilities narrow to what the backend allows
- route failures still surface inline so backend policy remains the source of truth

## Settings Tab

The settings tab has three sections:

- session: current backend URL, principal name, reconnect, and logout
- runtime settings: backend-backed editable fields such as currency defaults, model selection, memory, retry settings, and attachment limits
- diagnostics: environment, current principal, enabled models, and current attachment limits

## Files

- `ios/BillHelperFeatures/Sources/PlaceholderFeatures.swift`
- `ios/BillHelperApp/Sources/AppState.swift`
- `ios/BillHelperCore/Sources/APIClient+Finance.swift`
- `ios/BillHelperCore/Sources/APIClient+Catalogs.swift`
- `ios/BillHelperCore/Sources/FinanceSettingsModels.swift`
