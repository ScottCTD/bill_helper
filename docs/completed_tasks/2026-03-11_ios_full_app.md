# iOS Full App — Gap Analysis & Implementation Plan

Status: implemented and verified locally on 2026-03-11. This task doc is archived under `docs/completed_tasks/`.

## Problem Statement

The iOS app ships a Wave 2 MVP with three tabs (Dashboard, Entries, Agent). The backend
API exposes ~60 endpoints across 15 route families. The iOS app currently consumes **~15
of those endpoints** and has **read-only** access to most data. A fully-fledged iOS app
needs write capabilities, the remaining domain screens, and quality-of-life features users
expect on a native client.

---

## Gap Analysis

### A. Missing Domain Screens (no iOS surface at all)

| Domain | Backend endpoints | iOS status |
|---|---|---|
| **Accounts** | CRUD + snapshots + reconciliation (8 endpoints) | Dashboard shows reconciliation read-only; **no account list, create, edit, delete, or snapshot management** |
| **Entities** | list, create, update, delete (4 endpoints) | **Not exposed at all** |
| **Tags** | list, create, update, delete (4 endpoints) | **Not exposed at all** (tags display on entries only) |
| **Entry Groups** | CRUD + members (7 endpoints) | **Not exposed at all** |
| **Filter Groups** | CRUD (4 endpoints) | **Not exposed at all** |
| **Taxonomies** | list, terms CRUD (4 endpoints) | **Not exposed at all** |
| **Currencies** | list (1 endpoint) | **Not exposed at all** |
| **Users** | list, create, update (3 endpoints) | **Not exposed at all** |
| **Settings** | get, update (2 endpoints) | `runtimeSettings()` fetched but only used for agent config display |
| **Dashboard Timeline** | `GET /dashboard/timeline` (1 endpoint) | **Not consumed** |

### B. Missing Write/Mutate Operations on Existing Screens

| Screen | Current capability | Missing |
|---|---|---|
| **Entries** | Read-only list + detail | Create, edit, delete entries; tag assignment; group membership |
| **Dashboard** | Read-only month view | Month picker navigation; timeline chart; filter-group selection |
| **Agent** | Thread list, create, chat, review | Thread delete; thread rename; reopen rejected proposals; run event detail drill-down; tool-call inspection |

### C. Missing API Client Methods

The iOS `APIClient` currently implements ~15 methods. The following backend routes have no
corresponding client method:

```
Accounts:   POST /accounts, GET /accounts, PATCH /accounts/{id}, DELETE /accounts/{id}
            POST /accounts/{id}/snapshots, GET /accounts/{id}/snapshots,
            DELETE /accounts/{id}/snapshots/{id}, GET /accounts/{id}/reconciliation
Entities:   GET /entities, POST /entities, PATCH /entities/{id}, DELETE /entities/{id}
Tags:       GET /tags, POST /tags, PATCH /tags/{id}, DELETE /tags/{id}
Entries:    POST /entries, PATCH /entries/{id}, DELETE /entries/{id},
            GET /entries/{id} (detail)
Groups:     POST /groups, GET /groups, GET /groups/{id}, PATCH /groups/{id},
            DELETE /groups/{id}, POST /groups/{id}/members,
            DELETE /groups/{id}/members/{id}
Filters:    GET /filter-groups, POST /filter-groups, PATCH /filter-groups/{id},
            DELETE /filter-groups/{id}
Taxonomies: GET /taxonomies, GET /taxonomies/{key}/terms,
            POST /taxonomies/{key}/terms, PATCH /taxonomies/{key}/terms/{id}
Currencies: GET /currencies
Users:      GET /users, POST /users, PATCH /users/{id}
Settings:   PATCH /settings
Dashboard:  GET /dashboard/timeline
Agent:      DELETE /agent/threads/{id}, PATCH /agent/threads/{id},
            POST /agent/change-items/{id}/reopen,
            GET /agent/attachments/{id}, GET /agent/tool-calls/{id}
```

### D. Missing Platform Features

| Feature | Notes |
|---|---|
| **Authentication / Login** | Keychain stores a credential, but there is no login screen or token acquisition flow |
| **Onboarding** | No first-run setup, server URL config, or user selection |
| **Offline support** | No local caching or persistence layer |
| **Search** | No global or per-screen search |
| **Settings screen** | No UI to view/edit runtime settings |
| **Deep links** | No URL scheme or universal link handling |
| **Push notifications** | No remote notification support |
| **iPad / landscape** | No adaptive layout; phone-only today |
| **Error toasts / alerts** | Errors shown inline only; no global alert system |
| **Haptic feedback** | No tactile feedback on actions |
| **Accessibility** | No VoiceOver audit or Dynamic Type testing |

---

## Implementation Waves

### Wave 3 — Core Write Capabilities

> **Goal:** let users create and manage financial data natively, not just read it.

#### 3A: Entry Mutations
- Add `POST /entries`, `PATCH /entries/{id}`, `DELETE /entries/{id}` to `APIClient`
- Entry create form: amount, kind (expense/income/transfer), date, currency, entity selection, tag multi-select, notes
- Entry edit form: pre-populated with existing data
- Swipe-to-delete on entry list rows with confirmation
- Add `GET /entries/{id}` (detail endpoint) to `APIClient`
- Navigate entry detail to editable mode

#### 3B: Dashboard Enhancements
- Month picker (forward/back arrows or date wheel)
- Consume `GET /dashboard/timeline` and display chart (daily spend sparkline or bar chart)
- Filter-group selector to scope dashboard data (requires filter-group API integration)

#### 3C: Agent Completeness
- Thread rename (inline title edit → `PATCH /agent/threads/{id}`)
- Thread delete with confirmation (swipe-to-delete → `DELETE /agent/threads/{id}`)
- Reopen rejected proposals (`POST /agent/change-items/{id}/reopen`)
- Tool-call detail drill-down (`GET /agent/tool-calls/{id}`)
- Attachment viewer (`GET /agent/attachments/{id}`)

### Wave 4 — Catalog & Reference Screens

> **Goal:** expose the remaining domain management screens.

#### 4A: Accounts Screen (new tab or section)
- Account list view (`GET /accounts`)
- Account detail with snapshots timeline (`GET /accounts/{id}/snapshots`)
- Reconciliation view (`GET /accounts/{id}/reconciliation`)
- Account create / edit / delete forms
- Add / delete snapshots

#### 4B: Entities Screen
- Entity list with search/filter
- Entity create / edit / delete
- Link to entries that reference the entity

#### 4C: Tags Screen
- Tag list with color swatches
- Tag create / edit / delete (enforce no-entry-referencing guard from backend)
- Tag assignment from entry forms

#### 4D: Settings Screen
- Display current runtime settings
- Edit key settings (model name, currency, timezone, agent limits)
- `PATCH /settings` integration

### Wave 5 — Organization & Power Features

> **Goal:** match the web frontend's advanced organization capabilities.

#### 5A: Entry Groups
- Group list view (BUNDLE / SPLIT / RECURRING types)
- Group detail with member list
- Create / edit / delete groups
- Add / remove members

#### 5B: Filter Groups
- Filter group list
- Filter group builder (rule composition UI)
- Dashboard integration (select active filter group)

#### 5C: Taxonomies
- Taxonomy browser (entity_category, tag_type, etc.)
- Term management (add, edit, reorder)
- Assignment UI within entity and tag forms

#### 5D: Currencies & Users
- Currency catalog (read-only reference list)
- User list / create / admin toggle (admin-only)

### Wave 6 — Platform Polish

> **Goal:** production-quality native experience.

#### 6A: Authentication & Onboarding
- Login screen with server URL configuration
- User selection or creation on first launch
- Bearer token acquisition flow (if auth backend exists) or principal selection
- Secure token refresh

#### 6B: Search & Navigation
- Global search bar (entries, entities, tags, accounts)
- Deep link support (`billhelper://entries/{id}`, etc.)
- Recent items / quick actions

#### 6C: Offline & Performance
- Local SQLite cache for entries, accounts, tags
- Optimistic UI updates for mutations
- Background sync when network returns
- Image caching for agent attachments

#### 6D: iPad & Accessibility
- Adaptive layouts (sidebar navigation on iPad)
- Landscape support
- VoiceOver labels and hints audit
- Dynamic Type support verification
- Haptic feedback on create/delete/approve/reject

#### 6E: Notifications & Widgets
- Push notifications for agent run completion
- Home screen widget for daily spend summary
- Shortcut actions (Siri shortcuts for "add expense")

---

## Models to Add

New Swift model structs needed (not yet in `FinanceModels.swift` or `AgentModels.swift`):

```
Account, AccountCreate, AccountUpdate, AccountSnapshot, AccountSnapshotCreate
Entity, EntityCreate, EntityUpdate
TagCreate, TagUpdate
EntryCreate, EntryUpdate
EntryGroup, EntryGroupCreate, EntryGroupUpdate, EntryGroupMember
FilterGroup, FilterGroupCreate, FilterGroupUpdate, FilterRule
Taxonomy, TaxonomyTerm, TaxonomyTermCreate, TaxonomyTermUpdate
TaxonomyAssignment
Currency
User, UserCreate, UserUpdate
DashboardTimeline, DashboardTimelinePoint
```

---

## Testing Strategy

- Each new `APIClient` method gets a unit test with mock transport (existing pattern)
- Each new ViewModel gets state-machine tests (idle → loading → loaded/failed)
- Snapshot tests for new list/detail screens (optional, deferred)
- Integration test target against local dev server (manual, not CI)

---

## Files Affected

| Area | Files |
|---|---|
| Models | `BillHelperCore/Sources/FinanceModels.swift` (split if too large) |
| API | `BillHelperCore/Sources/APIClient.swift` |
| Features | `BillHelperFeatures/Sources/` — new feature files per domain |
| Navigation | `BillHelperApp/Sources/AppShellView.swift` (add tabs/sections) |
| Composition | `BillHelperApp/Sources/AppConfiguration.swift` (wire new ViewModels) |
| Tests | `BillHelperAPITests/` — new test files per feature |
| Docs | `ios/docs/` — new doc per wave |
