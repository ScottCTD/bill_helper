# iOS App Design TODO

## Goal

Add a minimal iOS client for Bill Helper while keeping the repository as a monorepo and avoiding a rewrite of the current backend/frontend architecture.

The iOS app should feel modern, calm, and native to current Apple platform expectations rather than like a cramped port of the desktop web UI.

## Recommendation Summary

- Keep the repo as a monorepo.
- Add a new top-level iOS app directory.
- Prefer `ios/` over `ios_app/`.
- Build the first version as a native SwiftUI app that talks to the existing backend API.
- Keep the first release narrow but useful: dashboard, entries, and a focused agent workflow with attachment upload.
- Treat invoice/receipt upload through the agent as an MVP requirement, not a phase-2 extra.
- Include multi-thread agent UX in MVP.
- Include approve/reject review actions for agent proposals in MVP.
- Treat modern visual quality and native-feeling mobile UX as first-class requirements for MVP.

## Why Monorepo Still Fits

A monorepo matches the current project shape:

- `backend/`: FastAPI API and domain logic
- `frontend/`: React web client
- `docs/`: architecture and execution plans

Adding iOS here keeps product code, API docs, and mobile planning in one place. It also makes it easier to evolve the backend and iOS client together, especially while the API and auth model are still changing.

## Folder Naming Discussion

### Option A: `ios/` (recommended)

Pros:

- conventional and easy to scan
- leaves room for a future `android/`
- matches the current concise top-level naming (`backend/`, `frontend/`, `docs/`)
- avoids embedding implementation detail in the folder name

Cons:

- slightly ambiguous if the folder later contains shared Apple-platform code beyond the app target

### Option B: `ios_app/`

Pros:

- explicit that this is an application, not generic platform support

Cons:

- less conventional
- longer and noisier at the repo root
- awkward if later paired with `android_app/`

### Option C: `apps/ios/`

Pros:

- best if we expect multiple product clients soon (`apps/web`, `apps/ios`, `apps/android`)

Cons:

- does not match the current repo layout
- would imply a broader root reorganization that is not needed yet

## Decision

Use a new top-level `ios/` directory for the first iOS app.

If the repo later grows into multiple app clients, we can reconsider a broader `apps/*` migration, but we should not pay that reorganization cost now.

## Product Direction

The minimal iOS app should be a focused client over the existing API, not a full local-first native port.

Why:

- the current system is centered on FastAPI + SQLite + local file storage
- the frontend already proves the backend API shape
- a true on-device local-first iOS port would require much larger storage, sync, and auth decisions

## Proposed MVP Scope

### Include

- dashboard read-only summary
- entries list
- multi-thread agent thread list and thread detail UX
- send agent messages
- upload invoice / receipt images and PDFs to the agent
- view agent responses and basic run state
- view pending agent proposals
- approve or reject agent proposals from mobile
- basic sign-in / authenticated session once auth exists

### Defer

- groups graph workspace
- properties/admin management
- runtime settings editor
- direct manual entry create/edit flows beyond what the agent enables
- advanced agent timeline details and tool-call inspection beyond the review flow needed for MVP

## Architecture Direction

## UX / Design Direction

- modern, native-feeling SwiftUI surfaces rather than a direct copy of the web layout
- mobile-first information density; avoid desktop-style cramped tables where cards or grouped lists are clearer
- polished core states: loading, empty, error, uploading, streaming, success, and review-pending
- strong support for attachments and agent activity as primary mobile actions
- clear typography, spacing, and hierarchy that feel current on iPhone
- prefer fewer screens done well over broad feature parity with weak mobile ergonomics

## Architecture Direction

### iOS client

- native SwiftUI app
- `URLSession` networking layer
- typed API models mapped from current backend contracts
- Keychain-backed auth token storage
- light view-model layer per feature
- multipart upload support for agent attachments
- SSE or polling-based run-status handling for agent responses
- review-action API integration for approve/reject flows

### Backend expectations before real mobile rollout

- real authentication instead of only principal-header identity
- HTTPS-accessible deployment model
- clear mobile-safe API base URL configuration
- review of admin-only endpoints for mobile exposure

## Proposed Repo Shape

```text
/backend
/frontend
/ios
/docs
/scripts
```

Inside `ios/`:

```text
/ios
  /BillHelperApp
  /BillHelperApp.xcodeproj
  /BillHelperCore
  /BillHelperFeatures
  /BillHelperAPITests
```

Initial intent:

- `BillHelperApp`: app entry, navigation, app wiring
- `BillHelperCore`: networking, models, auth/session, formatting utilities
- `BillHelperFeatures`: dashboard, entries, and agent multi-thread chat/upload/review flows
- `BillHelperAPITests`: small integration/contract coverage for API decoding

This can start as a single Xcode target and split only when the structure becomes durable.

## Implementation Phases

### Phase 0: backend readiness

- decide deployment model: hosted backend vs LAN-only prototype
- design proper auth flow for mobile
- confirm the exact endpoints needed for MVP
- confirm mobile handling for agent uploads, streaming, and attachment size/error states
- confirm the review endpoints and payloads needed for mobile approve/reject actions

### Phase 1: iOS shell

- create `ios/` project
- app navigation shell
- environment config for API base URL
- auth/session plumbing
- shared API client, multipart upload helper, and agent event transport choice
- shared review-action client methods and state handling for proposal approvals/rejections

### Phase 2: MVP features

- dashboard read model
- entries list
- multi-thread agent thread list and thread detail surface
- invoice / receipt upload flow
- agent response rendering and basic run lifecycle states
- proposal list / review surface inside each thread
- approve/reject actions for pending proposals

### Phase 3: polish and expansion

- entry detail read view
- manual entry create/edit flows outside the agent
- richer run-event and tool-call inspection
- more advanced agent composer ergonomics and attachment management

## Resolved Product Decisions

- agent review approve/reject is part of MVP
- multi-thread agent UX is part of MVP
- invoice and receipt upload through the agent is part of MVP
- modern visual quality and native-feeling UX are part of MVP

## Open Questions

- Is the first iOS build only for personal/internal use, or intended for App Store distribution?
- Will the phone connect to a hosted backend, or to a machine on the same LAN?
- Do we want iPhone-only first, or universal iPhone + iPad layout from day one?
- Do we need proposal payload editing on mobile MVP, or is approve/reject-only sufficient for v1?

## TODO Checklist

- [ ] confirm top-level folder name (`ios/`)
- [ ] confirm SwiftUI over wrapper-based approach
- [ ] define mobile MVP screens and exclude non-MVP surfaces
- [ ] design auth approach for remote/mobile use
- [ ] list backend/API changes required for mobile
- [ ] define the mobile agent scope in detail: thread list, thread detail, message send, upload, streaming/polling, and review UX
- [ ] confirm attachment constraints and upload UX for invoices/receipts on iPhone
- [ ] define explicit mobile design principles for a modern look and feel before implementation starts
- [ ] prioritize polished loading/empty/error/upload/review states in the MVP screen specs
- [ ] decide whether mobile MVP supports approve/reject only or proposal payload editing too
- [ ] create `ios/` project scaffold
- [ ] document local iOS dev workflow in `README.md` and `docs/development.md`
- [ ] update stable docs after implementation starts

## Current Recommendation To Follow

Proceed with a monorepo-native `ios/` directory and a small SwiftUI client over the existing backend, with the MVP centered on dashboard, entries, and multi-thread agent-based invoice/receipt submission plus mobile review actions, all delivered with a modern iPhone-native feel.
