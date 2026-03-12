# API Catalogs And Settings

Protected routes in this family require `Authorization: Bearer <token>`.

## Auth

### `POST /auth/login`

Create a password-backed session.

Body:

- `username`
- `password`

Response: `AuthLoginResponse`

Behavior:

- returns an opaque session token plus current user metadata

Errors:

- `403` invalid credentials
- `403` password reset required for this user

### `POST /auth/logout`

Revoke the current password session. Response: `204`

Behavior:

- requires an authenticated session
- deletes the current `sessions` row

### `GET /auth/me`

Return the authenticated session view. Response: `AuthSessionRead`

Returned fields include:

- `user`
- `session_id`
- `is_admin_impersonation`

## Admin

All `/admin/*` routes require an authenticated admin principal.

### `GET /admin/users`

List all users. Response: `UserRead[]`

Each row includes:

- `id`
- `name`
- `is_admin`
- `is_current_user`
- `account_count`
- `entry_count`

### `POST /admin/users`

Create a user. Response: `201 UserRead`

Body:

- `name`
- `password`
- `is_admin` (optional, default `false`)

### `PATCH /admin/users/{user_id}`

Update a user. Response: `UserRead`

Body fields:

- `name`
- `is_admin`

Errors:

- `422` when no updatable fields are provided

### `POST /admin/users/{user_id}/reset-password`

Set a new password for a user. Response: `UserRead`

Body:

- `new_password`

### `DELETE /admin/users/{user_id}`

Delete a user and all owned resources. Response: `204`

Behavior:

- cascades through owned accounts, entries, groups, entities, tags, taxonomies, filter groups, agent threads, and sessions

### `POST /admin/users/{user_id}/login-as`

Create an impersonation session for another user. Response: `AuthLoginResponse`

Behavior:

- returns a new password-mode bearer token
- response `is_admin_impersonation=true`
- intended for web-admin or API tooling flows that need the target user's exact scope

### `GET /admin/sessions`

List active sessions. Response: `AdminSessionRead[]`

Each row includes:

- session id and user id
- `user_name`
- `is_admin`
- `is_admin_impersonation`
- `created_at`
- `expires_at`
- `is_current`

### `DELETE /admin/sessions/{session_id}`

Revoke one session. Response: `204`

Errors:

- `404` session not found

## Users

### `GET /users`

List visible users. Response: `UserRead[]`

Behavior:

- admin principals receive all users
- non-admin principals receive only their own row
- kept as an authenticated user visibility read; user mutation routes live under `/admin`

### `POST /users/me/change-password`

Rotate the current user's password. Response: `204`

Body:

- `current_password`
- `new_password`

Errors:

- `403` when the current password is wrong
- `403` when the account is in reset-required state

## Entities

### `GET /entities`

List entities with usage counters. Response: `EntityRead[]`

Behavior:

- non-admin principals see only their own entities
- admin principals see all entities across users
- each row includes `is_account`
- usage counters (`from_count`, `to_count`, `account_count`, `entry_count`) follow the same principal scope as `/entries` and `/accounts`
- `net_amount_minor` and `net_amount_currency_code` are populated only when the visible referenced entries all share one currency
- `net_amount_mixed_currencies=true` means the entity has visible entries across multiple currencies, so no single aggregate amount is returned
- account-backed entities must be managed through `/accounts`

### `POST /entities`

Create an entity. Response: `201 EntityRead`

Body:

- `name`
- `category` (optional)

Behavior:

- the new entity is always owned by the authenticated principal
- admins who need to create catalog items for another user should impersonate that user first
- `category="account"` is rejected with `409`; use `/accounts` for real accounts

### `PATCH /entities/{entity_id}`

Update entity name or category. Response: `EntityRead`

Behavior:

- lookup is principal-scoped
- admins may update any entity
- returns `409` if `category="account"` is requested
- returns `409` for account-backed entities
- returns `422` when no updatable fields are provided

### `DELETE /entities/{entity_id}`

Delete a non-account entity. Response: `204`

Behavior:

- lookup is principal-scoped
- clears taxonomy assignment and category mirror
- detaches `from_entity_id` and `to_entity_id` while preserving visible label text
- returns `409` for account-backed entities

## Tags

### `GET /tags`

List tags with non-deleted entry counts. Response: `TagRead[]`

Behavior:

- non-admin principals see only their own tags
- admin principals see all tags
- `entry_count` follows the caller's visible non-deleted entries
- entry payloads still embed `TagSummaryRead` instead of repeating catalog counts

### `POST /tags`

Create a tag. Response: `201 TagRead`

Body:

- `name`
- `color` (optional)
- `description` (optional)
- `type` (optional)

Behavior:

- the new tag is always owned by the authenticated principal
- duplicate detection is owner-local, not global

### `PATCH /tags/{tag_id}`

Update tag name, color, description, or type. Response: `TagRead`

Behavior:

- lookup is principal-scoped
- admins may update any tag
- returns `422` when no updatable fields are provided

### `DELETE /tags/{tag_id}`

Delete a tag. Response: `204`

Behavior:

- lookup is principal-scoped
- clears taxonomy-backed tag-type assignment
- succeeds even when entries still reference the tag
- junction rows are removed through `entry_tags` cascade

## Taxonomies

### `GET /taxonomies`

List the caller's taxonomy definitions. Response: `TaxonomyRead[]`

Behavior:

- ensures the caller's default taxonomies exist before reading
- current defaults include `entity_category` and `tag_type`

### `GET /taxonomies/{taxonomy_key}/terms`

List one taxonomy's terms with usage counts. Response: `TaxonomyTermRead[]`

Behavior:

- reads the caller's taxonomy by key
- admin principals can resolve a taxonomy by key outside their own scope only when the key is unique across all users; otherwise the API returns `409` and the admin should impersonate the target user

### `POST /taxonomies/{taxonomy_key}/terms`

Create a taxonomy term. Response: `201 TaxonomyTermRead`

Body:

- `name`
- `description` (optional)

Behavior:

- creates or reuses the caller's taxonomy definition for that key
- term uniqueness is per taxonomy, not global

Errors:

- `404` unknown taxonomy key
- `409` duplicate normalized term

### `PATCH /taxonomies/{taxonomy_key}/terms/{term_id}`

Rename one taxonomy term and optionally update description. Response: `TaxonomyTermRead`

Behavior:

- lookup follows the same principal-scoped taxonomy rules as term reads
- returns `409` for duplicate names

## Currencies

### `GET /currencies`

Return built-in plus discovered currency catalog. Response: `CurrencyRead[]`

## Settings

### `GET /settings`

Fetch effective runtime settings plus override metadata. Response: `RuntimeSettingsRead`

Response highlights:

- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- `agent_model`
- `entry_tagging_model`
- `available_agent_models`
- `agent_bulk_max_concurrent_threads`
- `agent_base_url`
- `agent_api_key_configured`
- `overrides`

Behavior:

- settings are global to the app instance, not per authenticated user
- `user_memory` is DB-backed only and returned as an ordered list of strings
- `available_agent_models` is DB-backed only and returned as an ordered list of model identifiers; the effective list always includes `agent_model`
- identity is not part of runtime settings anymore
- `entry_tagging_model` is DB-backed only, nullable, and must resolve to one of the effective `available_agent_models`; blank disables inline entry tag suggestion
- `agent_api_key` is never returned
- `agent_base_url` reflects only an explicit custom override from runtime settings or `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL`
- `agent_api_key_configured` reports whether an explicit override key exists or LiteLLM can resolve provider credentials for the selected model

### `PATCH /settings`

Partially update runtime settings overrides. Response: `RuntimeSettingsRead`

Authorization: admin principal only.

Updatable fields include:

- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- `agent_model`
- `entry_tagging_model`
- `available_agent_models`
- `agent_max_steps`
- `agent_bulk_max_concurrent_threads`
- retry policy fields
- image and attachment limit fields
- `agent_base_url`
- `agent_api_key`

Notes:

- `user_memory` must be sent as a JSON list of strings; empty list clears the override
- `available_agent_models` must be sent as a JSON list of strings; empty list clears the override
- `agent_base_url` must use `http` or `https` and cannot target localhost or non-public IP literals
- `agent_api_key` cannot be the masked sentinel value `***masked***`
