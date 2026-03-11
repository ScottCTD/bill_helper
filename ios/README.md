# iOS Client

This is the local entry point for the native SwiftUI iPhone client. The current app is a backend-backed five-tab shell with principal-based onboarding, management workspaces, and full agent/detail flows.

## Shipped App Behavior

- first launch shows onboarding for backend URL + principal name, then persists the base URL in app preferences and the session credential in Keychain
- the tab shell is `Dashboard`, `Entries`, `Agent`, `Manage`, and `Settings`, with one `NavigationStack` per tab
- dashboard loads `GET /dashboard/timeline` and `GET /dashboard`, then shows a centered month strip, KPI/projection cards, trend and breakdown charts, largest expenses, and reconciliation drill-ins
- entries supports search, multi-tag local filters, detail navigation, create/edit forms, searchable tag selection, direct-group assignment, markdown notes, and delete actions
- agent supports thread create/rename/delete, message-anchored run state, themed markdown rendering, attachment upload/download, hydrated tool-call detail, review approve/reject/reopen, and explicit access gating for non-admin principals
- manage exposes accounts, entities, tags, groups, filter groups, taxonomies, currencies, and users with native list/detail/form flows
- settings exposes session controls, runtime settings editing, and diagnostics for the current principal and agent limits
- the app handles `billhelper://...` deep links for dashboard month, entry detail, account detail, group detail, agent thread, and settings

## Folder structure

- `BillHelperApp/`: app entry, app-shell composition, and shared app resources
- `BillHelperCore/`: API client, finance/agent models, session infrastructure, transport, and upload support
- `BillHelperFeatures/`: SwiftUI feature surfaces for dashboard, entries, agent, manage, and settings workflows, including the extracted agent timeline/markdown support helpers
- `BillHelperAPITests/`: focused simulator-run tests for API, onboarding/session wiring, dashboard/entries, agent flows, upload support, and transport behavior
- `BillHelperApp.xcodeproj/`: Xcode project, workspace metadata, and shared scheme
- `docs/`: iOS-client-specific behavior notes for the shipped full app
- `build/`: generated local build output; not source-of-truth documentation or product code

## Verification

- docs sync: `uv run python scripts/check_docs_sync.py`
- focused iOS verification: `xcodebuild -project ios/BillHelperApp.xcodeproj -scheme BillHelperApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:BillHelperAPITests test`

## Run against a local backend

- the app defaults to `http://localhost:8000/api/v1`, but for iOS-local development prefer a high local port to avoid collisions with other work
- from the repo root, apply migrations if needed: `uv run alembic upgrade head`
- start the backend on the recommended iOS-local port: `uv run uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 48187 --reload`
- in the Xcode scheme environment, set `BILL_HELPER_API_BASE_URL=http://127.0.0.1:48187/api/v1` before launching the app if you want the onboarding form prefilled
- launch the app, enter the backend URL and a valid principal name, then tap `Test connection`
- after onboarding succeeds, every tab uses that saved backend URL until the session is changed in Settings

## Local docs

- start here for the local iOS overview
- see `../docs/ios_index.md` for the cross-repo iOS entry point
- see `docs/README.md` for iOS-specific detail docs
- see `docs/app-shell-and-session.md` for onboarding, tabs, and deep links
- see `docs/dashboard-entries.md` for dashboard and ledger behavior
- see `docs/manage-and-settings.md` for the manage tab and runtime settings surfaces
- see `docs/agent.md` for thread, upload, tool-call, and review behavior
