# Multi-User Security & Admin System

## Goal

Replace the development-only header-based auth with a real credential-based multi-user
system. Every resource becomes strictly user-scoped (no null-owned data). Admins can
manage all users and access all data through an admin panel.

## Auth Architecture

### Password Hashing: Argon2id

Use `argon2-cffi` with its built-in defaults (memory=65536 KiB, time=3, parallelism=4).
The hash output is self-describing — parameters are embedded in the hash string, so
future parameter upgrades don't invalidate existing hashes.

### Session Tokens: Opaque DB Tokens

Login produces a cryptographically random opaque token (e.g. `secrets.token_urlsafe(32)`).
Tokens are stored in a `sessions` table and looked up on every request. This makes
revocation trivial (delete the row) and gives admins visibility into active sessions.

No JWTs. No refresh tokens. One token per session.

### Auth Modes

Add `auth_mode: Literal["development_header", "password"]` to `Settings`.
`"password"` is the new default. `"development_header"` remains available for local dev.
The auth dependency switches behavior based on this setting.

## Database Changes

### New Tables

#### `users` — modify existing

Add columns:
- `password_hash` (`Text`, NOT NULL) — Argon2id hash string

#### `sessions` — new table

- `id` (PK UUID string)
- `user_id` (FK → `users.id`, NOT NULL, CASCADE delete)
- `token_hash` (String, NOT NULL, unique, indexed) — SHA-256 of the opaque token
- `created_at` (DateTime, NOT NULL)
- `expires_at` (DateTime, nullable) — null means no expiry
- `is_admin_impersonation` (Boolean, NOT NULL, default False) — marks sessions created via admin login-as

Store `SHA-256(token)` in the DB, not the raw token. The raw token is returned to the
client only once at login. This way a DB leak doesn't compromise active sessions.

### Schema Changes — Add `owner_user_id` (NOT NULL) Everywhere

Tables that currently lack `owner_user_id`:
- `entities` — add `owner_user_id` (FK → `users.id`, NOT NULL)
- `tags` — add `owner_user_id` (FK → `users.id`, NOT NULL)
- `taxonomies` — add `owner_user_id` (FK → `users.id`, NOT NULL)
- `taxonomy_terms` — inherits scope from parent taxonomy (no separate FK needed)
- `taxonomy_assignments` — inherits scope from parent taxonomy (no separate FK needed)
- `agent_threads` — add `owner_user_id` (FK → `users.id`, NOT NULL)
- `entry_tags` — inherits scope from entry (no separate FK needed)

Tables that currently have nullable `owner_user_id` — make NOT NULL:
- `accounts` (`owner_user_id` nullable → NOT NULL)
- `entries` (`owner_user_id` nullable → NOT NULL)
- `entry_groups` (`owner_user_id` nullable → NOT NULL)
- `filter_groups` (already NOT NULL — no change)

`account_snapshots` — inherits scope from parent account (no separate FK needed).

Cascade rule for all new/changed FKs: `ON DELETE CASCADE` (deleting a user deletes
all their data). Replace existing `ON DELETE SET NULL` rules with `CASCADE`.

### Migration Strategy

Single Alembic migration that:
1. Adds `password_hash` to `users` (with a temporary default for existing rows — the
   admin must reset passwords for all existing users after migration).
2. Creates `sessions` table.
3. Adds `owner_user_id` NOT NULL columns to `entities`, `tags`, `taxonomies`,
   `agent_threads`.
4. Makes existing nullable `owner_user_id` columns NOT NULL on `accounts`, `entries`,
   `entry_groups`.
5. Changes all `owner_user_id` FKs from `ON DELETE SET NULL` to `ON DELETE CASCADE`.

For step 3–4, the migration must assign all null-owned rows to a designated user
(the first admin user, or a configurable fallback). Fail loudly if no admin user exists.

### Uniqueness Constraints After User-Scoping

Several tables currently have global uniqueness constraints that must become per-user:
- `entities.name` — unique globally → unique per `(owner_user_id, name)`
- `tags.name` — unique globally → unique per `(owner_user_id, name)`
- `taxonomies.key` — unique globally → unique per `(owner_user_id, key)`
- `taxonomy_terms.(taxonomy_id, normalized_name)` — already scoped to taxonomy, no change needed
- `taxonomy_assignments` unique constraint — already scoped to taxonomy, no change needed

## Backend Changes

### Auth Layer (`backend/auth/`)

- **`dependencies.py`**: New `get_current_principal` dependency for `password` mode.
  Reads `Authorization: Bearer <token>` header, looks up `SHA-256(token)` in `sessions`
  table, returns `RequestPrincipal`. Returns 401 if missing/invalid/expired.
- **`dev_session.py`**: Keep as-is for `development_header` mode.
- **Remove auto-user creation**: `get_or_create_current_principal` → `get_current_principal`.
  Unknown users get 401, not auto-created.

### New Endpoints

#### Auth

- `POST /api/v1/auth/login` — body: `{username, password}`. Returns `{token, user}`.
  Public (no auth required).
- `POST /api/v1/auth/logout` — invalidates current session token. Requires auth.
- `GET /api/v1/auth/me` — returns current user info. Requires auth.

#### Admin User Management

All require admin principal:

- `POST /api/v1/admin/users` — create user with `{name, password, is_admin}`.
- `GET /api/v1/admin/users` — list all users with stats.
- `PATCH /api/v1/admin/users/{user_id}` — update name, is_admin.
- `POST /api/v1/admin/users/{user_id}/reset-password` — body: `{new_password}`.
- `DELETE /api/v1/admin/users/{user_id}` — deletes user + all data (CASCADE).
- `POST /api/v1/admin/users/{user_id}/login-as` — returns a session token for the
  target user (marked as `is_admin_impersonation=True`). Admin can browse as that user.
- `GET /api/v1/admin/sessions` — list active sessions across all users.
- `DELETE /api/v1/admin/sessions/{session_id}` — revoke a session.

#### User Self-Service

- `POST /api/v1/users/me/change-password` — body: `{current_password, new_password}`.

### Access Scope Overhaul (`backend/services/access_scope.py`)

Remove all null-owner fallback logic. Every filter becomes strict ownership:

```python
def owner_user_condition(owner_user_id_column, *, principal_user_id: str, is_admin: bool):
    if is_admin:
        return true()
    return owner_user_id_column == principal_user_id
```

No more `or_(... , owner_user_id_column.is_(None))`.

Add new scope filters for newly user-scoped tables:
- `entity_owner_filter(principal)` — filter `Entity.owner_user_id`
- `tag_owner_filter(principal)` — filter `Tag.owner_user_id`
- `taxonomy_owner_filter(principal)` — filter `Taxonomy.owner_user_id`
- `agent_thread_owner_filter(principal)` — filter `AgentThread.owner_user_id`

### Service Layer Changes

Every service that queries entities, tags, taxonomies, or agent threads must add the
corresponding owner filter. Key files:

- `backend/services/entities.py` — add `entity_owner_filter`
- `backend/services/tags.py` — add `tag_owner_filter`
- `backend/services/taxonomies.py` — add `taxonomy_owner_filter`
- `backend/routers/agent_threads.py` — add `agent_thread_owner_filter`
- `backend/services/entries.py` — already has `entry_owner_filter`, no null fallback
- `backend/services/accounts.py` — already has `account_owner_filter`, no null fallback
- All creation endpoints must set `owner_user_id = principal.user_id` on the new resource

### Router Changes

- Remove admin-only restriction on tag creation (`POST /tags`) — any user can create
  their own tags now.
- Remove admin-only restriction on entity creation if it exists.
- All CRUD endpoints must enforce ownership via scope filters (not just list endpoints).
- `GET /api/v1/auth/login` and `POST /api/v1/auth/login` are unprotected.
- `GET /healthz` remains unprotected.

### Config Changes (`backend/config.py`)

- `auth_mode` default: `"password"` (was `"development_header"`)
- Remove `current_user_name` setting (no longer meaningful — agent runs under the
  authenticated user's identity)
- Keep `development_admin_principal_names` for dev mode only

## Frontend Changes

### Login Page

- New route `/login` with username + password form.
- On success, store the opaque token in `localStorage` (key: `bill-helper.session-token`).
- Replace `X-Bill-Helper-Principal` header with `Authorization: Bearer <token>` in all
  API calls (`frontend/src/lib/api.ts`).
- On 401 response, redirect to `/login`.

### Remove Principal Session System

Delete or gut:
- `frontend/src/features/session/principalStorage.ts`
- `frontend/src/features/session/PrincipalSessionProvider.tsx`
- `frontend/src/features/session/PrincipalSessionGate.tsx`

Replace with a simpler `AuthProvider` that checks for a stored token and validates it
via `GET /api/v1/auth/me` on app startup.

### Admin Panel

New admin-only UI section (route: `/admin`):
- **User list** — table of all users with name, is_admin, account/entry counts.
- **Create user** — form with name, password, is_admin toggle.
- **Edit user** — rename, toggle admin.
- **Reset password** — set new password for any user.
- **Delete user** — with confirmation (warns about CASCADE data deletion).
- **Login as user** — button that calls `/admin/users/{id}/login-as`, stores the
  returned token, and redirects to the main app as that user. Show a banner indicating
  admin impersonation mode.
- **Active sessions** — list with revoke buttons.

### Self-Service

- **Change password** page/modal accessible from user menu.

## Agent System Changes

- `AgentThread` model: add `owner_user_id` (FK → `users.id`, NOT NULL).
- Agent thread creation (`POST /agent/threads`): set `owner_user_id = principal.user_id`.
- Agent thread listing: filter by `agent_thread_owner_filter(principal)`.
- Agent run execution: the agent operates under the authenticated user's scope — all
  tool calls (create entry, create tag, etc.) use the principal's `user_id`.
- Agent change item review: scoped to threads the principal owns (or admin sees all).

## Implementation Checklist

### Phase 1: Backend Auth Foundation
- [ ] Add `argon2-cffi` dependency
- [ ] Create Alembic migration: `password_hash` on `users`, `sessions` table
- [ ] Implement password hashing service (`backend/services/passwords.py`)
- [ ] Implement session service (`backend/services/sessions.py`)
- [ ] Add auth router (`backend/routers/auth.py`) — login, logout, me
- [ ] Update `backend/auth/dependencies.py` for `password` auth mode
- [ ] Add admin router (`backend/routers/admin.py`) — user CRUD, reset-password, login-as, session management
- [ ] Add `POST /api/v1/users/me/change-password` endpoint

### Phase 2: Universal User-Scoping
- [ ] Alembic migration: add `owner_user_id` NOT NULL to `entities`, `tags`, `taxonomies`, `agent_threads`
- [ ] Alembic migration: make `owner_user_id` NOT NULL on `accounts`, `entries`, `entry_groups`
- [ ] Alembic migration: change all `ON DELETE SET NULL` to `ON DELETE CASCADE`
- [ ] Alembic migration: change uniqueness constraints to per-user
- [ ] Update all models in `backend/models_finance.py` and `backend/models_agent.py`
- [ ] Overhaul `backend/services/access_scope.py` — remove null-owner fallback
- [ ] Add owner filters to entity, tag, taxonomy, agent thread services
- [ ] Update all service creation functions to set `owner_user_id`
- [ ] Remove admin-only restriction on tag/entity creation
- [ ] Remove auto-user creation from auth dependency

### Phase 3: Frontend
- [ ] Build login page + auth token storage
- [ ] Replace `X-Bill-Helper-Principal` with `Authorization: Bearer` in API client
- [ ] Remove principal session system (PrincipalSessionGate, principalStorage, etc.)
- [ ] Build `AuthProvider` with 401 redirect
- [ ] Build admin panel (user list, create, edit, delete, reset-password, login-as, sessions)
- [ ] Build change-password UI
- [ ] Add impersonation banner

### Phase 4: Verification
- [ ] Update all existing backend tests for new auth flow
- [ ] Write tests: login, logout, token validation, expiry
- [ ] Write tests: admin user CRUD, reset-password, login-as, session revocation
- [ ] Write tests: data isolation — user A cannot see user B's entities/tags/threads/etc.
- [ ] Write tests: cascade delete — deleting user removes all owned data
- [ ] Write tests: uniqueness is per-user (two users can have same tag name)
- [ ] `uv run python -m py_compile` on all touched modules
- [ ] `OPENROUTER_API_KEY=test uv run pytest backend/tests -q`
- [ ] `uv run python scripts/check_docs_sync.py`
- [ ] Manual smoke test: login, create data, login as different user, verify isolation

### Phase 5: Documentation
- [ ] Update `docs/data_model.md` — new tables, changed columns, cascade rules
- [ ] Update `docs/api.md` — new auth/admin endpoints, removed header auth
- [ ] Update relevant `backend/docs/*.md`
- [ ] Update `docs/repository_structure.md` if new files added
- [ ] Update `README.md` setup instructions (initial admin user creation)

## Design Decisions

1. **Argon2id over bcrypt** — OWASP #1 recommendation, memory-hard, GPU/ASIC resistant.
2. **Opaque DB tokens over JWT** — trivial revocation, admin session visibility,
   simpler impersonation. No key management.
3. **SHA-256 of token stored in DB** — raw token never persisted. DB leak doesn't
   compromise sessions.
4. **ON DELETE CASCADE everywhere** — deleting a user cleanly removes all their data.
   No orphaned records.
5. **No null-owned data** — every record has an explicit owner. Eliminates an entire
   class of data-leak bugs.
6. **Per-user uniqueness** — two users can independently have a tag named "food" or
   an entity named "Amazon". No cross-user name collisions.
7. **Admin impersonation via real session** — login-as creates an actual session token
   for the target user, so the admin sees exactly what that user sees. Marked with
   `is_admin_impersonation` for audit purposes.
8. **No rate limiting** — deferred. Prototype scope.
9. **No iOS changes** — deferred. iOS app can adopt bearer token auth later using its
   existing `SessionCredential.bearerToken` variant.

