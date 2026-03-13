# Backend Domain And HTTP

## Domain Models

- `backend/models_finance.py`: users, sessions, accounts, entities, tags, taxonomies, filter groups, entries, and groups
- `backend/models_agent.py`: agent threads, messages, attachments, runs, tool calls, change items, and review actions
- `backend/models_settings.py`: runtime settings overrides
- `backend/contracts_groups.py`: shared group write contracts
- `backend/contracts_users.py`: shared user and password contracts

Important ownership rules:

- owned finance resources carry non-null `owner_user_id`
- `users` own accounts, entries, groups, entities, tags, taxonomies, filter groups, agent threads, and sessions
- deleting a user cascades through owned resources
- account ids remain shared entity-root ids

## Auth Boundary

- `backend/auth/contracts.py`: bearer-auth and request-principal contracts
- `backend/auth/dependencies.py`: principal resolution from bearer session tokens
- `backend/services/passwords.py`: Argon2 password hashing and reset-required sentinel handling
- `backend/services/sessions.py`: opaque token creation, hashing, lookup, and revocation
- `backend/services/principals.py`: request-principal construction from a user row plus optional session row

Current behavior:

- `get_current_principal()` never auto-creates users
- protected routes require `Authorization: Bearer <token>`
- admin checks rely on persisted `users.is_admin`

## Schemas

- `backend/schemas_finance.py`: ledger, group, filter-group, dashboard, and visible-user contracts
- `backend/schemas_agent.py`: thread, message, run, change-item, and review contracts
- `backend/schemas_settings.py`: runtime settings request/response contracts
- `backend/schemas_auth.py`: login, session, admin-user, and admin-session contracts

Important read models:

- `UserRead` for visible-user selectors and admin user lists
- `AccountRead` and `EntryRead` with non-null `owner_user_id`
- `RuntimeSettingsRead` without identity fields
- `AuthSessionRead` / `AuthLoginResponse` for session-backed auth

## Core Services

- `backend/services/accounts.py`
- `backend/services/entries.py`
- `backend/services/entities.py`
- `backend/services/tags.py`
- `backend/services/taxonomy.py`
- `backend/services/groups.py`
- `backend/services/filter_groups.py`
- `backend/services/finance.py`
- `backend/services/users.py`
- `backend/services/access_scope.py`
- `backend/services/runtime_settings.py`

Shared policy helpers:

- `crud_policy.py`: validation/conflict helpers and `PolicyViolation`
- `access_scope.py`: canonical owner/admin query filters and scoped loaders
- `finance_contracts.py`: service-owned account/entity/tag write commands

Auth- and user-management services:

- `users.py`: authenticate, create/update/delete users, change/reset passwords, and visible-user reads
- `passwords.py`: password hash generation and verification
- `sessions.py`: session creation and revocation

## Routers

Mixed auth router:

- `backend/routers/auth.py`: `POST /auth/login` is public; `POST /auth/logout` and `GET /auth/me` require a bearer-authenticated principal

Protected routers:

- `backend/routers/admin.py`: admin user/session management and impersonation
- `backend/routers/users.py`: `GET /users` and `POST /users/me/change-password`
- `accounts.py`
- `entries.py`
- `groups.py`
- `dashboard.py`
- `filter_groups.py`
- `entities.py`
- `tags.py`
- `taxonomies.py`
- `currencies.py`
- `settings.py`
- split agent routers under `backend/routers/agent_*`

Router behavior:

- routers own HTTP translation only
- all protected routers depend on `get_current_principal`
- finance, catalog, and agent lookups are owner-scoped through `access_scope.py`
- non-admin principals are restricted to their own owned resources
- admin principals can read and mutate all owned resources
- account and entry create/update flows default `owner_user_id` to the current principal unless an admin explicitly assigns another user on supported finance routes
- entity, tag, and taxonomy mutations are authenticated-user accessible and create records for the caller's own scope
- settings writes stay admin-only because runtime settings are app-global

## Agent HTTP Ownership

Agent routes are no longer admin-only.

Current rules:

- threads are owned by `agent_threads.owner_user_id`
- runs, tool calls, change items, and attachments inherit access through the parent thread
- review apply uses the approving principal for scoped resolution and owner attribution

## Related Docs

- `docs/api/core_ledger.md`
- `docs/api/catalogs_and_settings.md`
- `docs/api/agent.md`
- `docs/data_model.md`
