# Frontend Client And State

## Shared Client Layer

### `frontend/src/lib/types.ts`

Defines typed API models for:

- ledger domain (`Entry`, `Account`, `User`, `Entity`, `Tag`, ...)
- analytics (`Dashboard`, `Reconciliation`, ...)
- runtime settings (`RuntimeSettings`, `RuntimeSettingsOverrides`)
- agent domain (`AgentThread*`, `AgentMessage*`, `AgentRun`, `AgentToolCall`, `AgentChangeItem`, `AgentReviewAction`)

Current contract highlights:

- `Account` no longer exposes `entity_id`
- `Entity` includes `is_account` plus single-currency net aggregate fields for the standalone entities table
- `User` includes persisted `is_admin` and `is_current_user`
- `Entry` and `EntryDetail` include `from_entity_missing` and `to_entity_missing`
- runtime settings include both `agent_model` and ordered `available_agent_models`

### `frontend/src/lib/api.ts`

Responsibilities:

- generic `request<T>` helper
- JSON and FormData request handling
- injects `X-Bill-Helper-Principal` from the shared frontend principal session before every protected request
- endpoint functions across all backend domains including `agent/*`
- runtime settings client methods:
  - `getRuntimeSettings`
  - `updateRuntimeSettings`
  - `updateRuntimeSettings` uses a typed runtime-settings patch payload that mirrors the backend `PATCH /settings` contract
- taxonomy client methods:
  - `listTaxonomies`
  - `listTaxonomyTerms`
  - `createTaxonomyTerm`
  - `updateTaxonomyTerm`
- property delete client methods:
  - `deleteAccount`
  - `deleteEntity`
  - `deleteTag`
- group client methods:
  - `listGroups`
  - `getGroup`

### `frontend/src/lib/queryKeys.ts`

Responsibilities:

- centralized TanStack Query key factory by domain
- stable key shapes for list, detail, thread, and derived queries
- groups keys include `groups.list` and `groups.detail(groupId)`
- properties keys include taxonomy-specific keys
- settings keys include `settings.runtime`

### `frontend/src/lib/queryInvalidation.ts`

Responsibilities:

- centralized invalidation policies after writes and review actions
- shared invalidation bundles for entry, account, agent, and property read models
- runtime settings invalidation refreshes dependent surfaces after settings writes
- taxonomy invalidation refreshes term usage and dependent lists
- account, entity, and tag delete invalidation refreshes accounts, properties, entries, and dashboard surfaces that depend on preserved labels or cascaded tag detaches

## State Strategy

- TanStack Query owns remote server state
- feature-owned hooks under `frontend/src/features/*` own screen-level derived state and mutations
- query keys and invalidation logic should be reused rather than recreated ad hoc in pages or components

## Principal Session

- `frontend/src/features/session/principalStorage.ts`
  - localStorage-backed principal session state, shared header constant, and browser-change event
- `frontend/src/features/session/PrincipalSessionProvider.tsx`
  - app-wide principal session context for reading, updating, and clearing the active principal
- `frontend/src/features/session/PrincipalSessionGate.tsx`
  - startup gate that blocks protected workspace rendering until a principal session exists
- `frontend/src/features/session/PrincipalSessionCard.tsx`
  - sidebar control for switching or clearing the active principal without rebuilding request code per page
