# iOS Client

This is the main local entry point for the native iOS client shipped in this repository. The current target is an internal SwiftUI iPhone MVP that talks to the existing Bill Helper backend.

## Shipped MVP behavior

- dashboard tab loads the current-month backend dashboard and shows summary cards, KPI tiles, top spending, largest expenses, and reconciliation state
- entries tab loads backend entries, shows a mobile-first list, supports pull-to-refresh, and opens a read-only detail view from loaded row data
- agent tab shows thread list/detail flows with loading, empty, error, and refresh states
- creating a thread pushes directly into thread detail for immediate messaging
- thread detail shows assistant/user messages, run state, recent streamed text/reasoning, and pending review cards
- assistant message bubbles render markdown formatting from the backend `contentMarkdown` field while user/system messages stay plain text
- composer supports text send plus invoice/receipt attachments from Photos or the file importer
- approve/reject proposal review actions update thread detail immediately and refresh parent-list summaries
- app startup restores persisted session state before wiring the live client, and app configuration resolves the backend base URL for MVP development

## Folder structure

- `BillHelperApp/`: app entry, app-shell composition, and shared app resources
- `BillHelperCore/`: API client, finance/agent models, session infrastructure, transport, and upload support
- `BillHelperFeatures/`: SwiftUI feature surfaces for dashboard, entries, and agent workflows
- `BillHelperAPITests/`: focused simulator-run tests for API, app configuration, dashboard/entries, agent flows, upload support, and transport behavior
- `BillHelperApp.xcodeproj/`: Xcode project, workspace metadata, and shared scheme
- `docs/`: iOS-client-specific behavior notes for shipped MVP screens and flows
- `build/`: generated local build output; not source-of-truth documentation or product code

## Verification

- docs sync: `uv run python scripts/check_docs_sync.py`
- focused iOS verification: `xcodebuild -project ios/BillHelperApp.xcodeproj -scheme BillHelperApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:BillHelperAPITests test`

## Run against a local backend

- the app defaults to `http://localhost:8000/api/v1`, but for iOS-local development prefer a high local port to avoid collisions with other work
- from the repo root, apply migrations if needed: `uv run alembic upgrade head`
- start the backend on the recommended iOS-local port: `uv run uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 48187 --reload`
- in the Xcode scheme environment, set `BILL_HELPER_API_BASE_URL=http://127.0.0.1:48187/api/v1` before launching the app
- after the backend is running and the environment variable is set, the dashboard, entries, and agent flows will read from that local backend

## Local docs

- start here for the local iOS overview
- see `docs/README.md` for iOS-specific detail docs
- see `docs/dashboard-and-entries-mvp.md` for dashboard and entries behavior
- see `docs/agent-mvp.md` for thread, upload, run-state, and review behavior

