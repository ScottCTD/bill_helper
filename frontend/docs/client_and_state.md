# Frontend Client And State

## Shared Client Layer

### `frontend/src/lib/types.ts`

Defines typed API models for:

- ledger domain (`Entry`, `Account`, `User`, `Entity`, `Tag`, ...)
- analytics (`Dashboard`, `Reconciliation`, ...)
- auth/admin (`AuthSession`, `AuthLoginResponse`, `AdminSession`)
- runtime settings (`RuntimeSettings`, `RuntimeSettingsOverrides`)
- agent domain (`AgentThread*`, `AgentMessage*`, `AgentRun`, `AgentToolCall`, `AgentChangeItem`, `AgentReviewAction`)

Current contract highlights:

- `Account.owner_user_id` and `Entry.owner_user_id` are non-null
- `RuntimeSettings` no longer carries identity fields
- auth payloads include impersonation metadata

### `frontend/src/lib/api.ts`

Responsibilities:

- generic `request<T>` helper
- JSON and FormData request handling
- injects `Authorization: Bearer <token>` from `localStorage` before protected requests
- clears the stored token on `401`
- exposes route helpers across ledger, catalog, settings, agent, auth, and admin domains

Notable client methods:

- auth:
  - `login`
  - `logout`
  - `getAuthSession`
- admin:
  - `listAdminUsers`
  - `createAdminUser`
  - `updateAdminUser`
  - `resetAdminUserPassword`
  - `deleteAdminUser`
  - `loginAsAdminUser`
  - `listAdminSessions`
  - `deleteAdminSession`

### `frontend/src/lib/queryKeys.ts`

Responsibilities:

- centralized TanStack Query key factory
- stable domains for auth, admin, settings, ledger, properties, dashboard, and agent data

Current auth-related keys:

- `auth.session`
- `admin.users`
- `admin.sessions`

## State Strategy

- TanStack Query owns remote server state
- feature hooks under `frontend/src/features/*` own screen-level derived state and mutations
- auth session state lives outside Query in the auth provider because it must survive redirects and global `401` handling

## Auth State

- `frontend/src/features/auth/storage.ts`
  - `localStorage` helpers around `bill-helper.session-token`
- `frontend/src/features/auth/AuthProvider.tsx`
  - app-wide auth context for loading `/auth/me`, logging in, logging out, and adopting impersonation sessions
- `frontend/src/features/auth/AuthSessionCard.tsx`
  - sidebar logout item that includes the signed-in username in expanded mode
- `frontend/src/components/Sidebar.tsx`
  - renders the dedicated admin footer button separately from the logout item

Current behavior:

- app startup validates any stored token with `GET /auth/me`
- invalid or expired tokens are cleared automatically
- successful admin impersonation swaps the stored token and refreshes the whole app scope
