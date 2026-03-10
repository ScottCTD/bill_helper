# API Catalogs And Settings

Protected routes in this family require `X-Bill-Helper-Principal`. Missing the header returns `401`.

## Users

### `GET /users`

List users. Response: `UserRead[]`

Behavior:

- admin principal returns all users
- non-admin principal returns only the caller row
- each row includes persisted `is_admin` plus `is_current_user`

### `POST /users`

Create user. Response: `UserRead`

Errors: `400` empty name, `409` duplicate.

Authorization: admin principal only.

### `PATCH /users/{user_id}`

Update user. Response: `UserRead`

Behavior: non-admin principal may update only itself.

Errors:

- `422` when no updatable fields are provided

## Entities

### `GET /entities`

List entities with usage counters. Response: `EntityRead[]`

Behavior:

- each row includes `is_account`
- admin principals see every entity plus global usage counters
- non-admin principals still see shared non-account entities, but account-backed entities are limited to the caller's own visible accounts
- non-admin usage counters (`from_count`, `to_count`, `account_count`, `entry_count`) and entity net aggregates follow the same owner scope as `/entries` and `/accounts`
- `net_amount_minor` and `net_amount_currency_code` are populated only when the visible referenced entries all share one currency
- `net_amount_mixed_currencies=true` means the entity has visible entries across multiple currencies, so no single aggregate amount is returned
- account-backed entities must be managed through `/accounts`

### `POST /entities`

Create entity.

Body:

- `name`
- `category` (optional)

Response: `EntityRead`

Authorization: admin principal only.

Errors: `400` empty name, `409` duplicate normalized name.

Behavior:

- `category="account"` is rejected with `409`; use `/accounts` for real accounts

### `PATCH /entities/{entity_id}`

Update entity name or category. Response: `EntityRead`

Authorization: admin principal only.

Behavior:

- response category is resolved from taxonomy assignments
- returns `409` if `category="account"` is requested
- returns `409` for account-backed entities
- returns `422` when no updatable fields are provided

### `DELETE /entities/{entity_id}`

Delete a non-account entity. Response: `204`

Authorization: admin principal only.

Behavior:

- clears taxonomy assignment and category mirror
- detaches `from_entity_id` and `to_entity_id` while preserving visible label text
- returns `409` for account-backed entities

## Tags

### `GET /tags`

List tags with non-deleted entry counts. Response: `TagRead[]`

Behavior:

- admin principals see global `entry_count`
- non-admin `entry_count` reflects only the caller's visible non-deleted entries
- this catalog contract is only used by `/tags`; entry payloads embed `TagSummaryRead` instead of repeating catalog counts

### `POST /tags`

Create tag.

Body:

- `name`
- `color` (optional)
- `description` (optional)
- `type` (optional)

Response: `TagRead`

Errors: `400` empty name, `409` duplicate.

Authorization: admin principal only.

### `PATCH /tags/{tag_id}`

Update tag name, color, description, or type. Response: `TagRead`

Authorization: admin principal only.

Errors:

- `422` when no updatable fields are provided

### `DELETE /tags/{tag_id}`

Delete tag. Response: `204`

Authorization: admin principal only.

Behavior:

- clears taxonomy-backed tag-type assignment
- succeeds even when entries still reference the tag
- entry/tag associations are removed through `entry_tags` cascade rows

## Taxonomies

### `GET /taxonomies`

List taxonomy definitions. Response: `TaxonomyRead[]`

Current defaults include `entity_category` and `tag_type`.

### `GET /taxonomies/{taxonomy_key}/terms`

List one taxonomy's terms with usage counts. Response: `TaxonomyTermRead[]`

### `POST /taxonomies/{taxonomy_key}/terms`

Create a normalized taxonomy term. Response: `TaxonomyTermRead`

Errors: `400`, `404`, `409` depending on invalid taxonomy key, missing taxonomy, or duplicate term.

Authorization: admin principal only.

### `PATCH /taxonomies/{taxonomy_key}/terms/{term_id}`

Rename one taxonomy term and optionally update description. Response: `TaxonomyTermRead`

Authorization: admin principal only.

## Currencies

### `GET /currencies`

Return built-in plus discovered currency catalog. Response: `CurrencyRead[]`

## Settings

### `GET /settings`

Fetch effective runtime settings plus override metadata. Response: `RuntimeSettingsRead`

Response highlights:

- `current_user_name` resolved from request principal
- `user_memory` (`string[] | null` of persistent memory items)
- `default_currency_code`
- `dashboard_currency_code`
- agent runtime fields
- `agent_model`
- `available_agent_models`
- `agent_bulk_max_concurrent_threads`
- `agent_base_url`
- `agent_api_key_configured`
- `overrides` object with nullable override values

Behavior:

- `user_memory` is DB-backed only and returned as an ordered list of strings
- `available_agent_models` is DB-backed only and returned as an ordered list of model identifiers; the effective list always includes `agent_model`
- `current_user_name` comes from the explicit request principal, not mutable runtime settings state
- `agent_api_key` is never returned
- `agent_base_url` reflects only an explicit custom override from runtime settings or `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL`
- `agent_api_key_configured` reports whether an explicit override key exists or LiteLLM can resolve provider credentials for the selected model; `overrides.agent_api_key_configured` reports only whether a stored runtime override exists

### `PATCH /settings`

Partially update runtime settings overrides. Response: `RuntimeSettingsRead`

Updatable fields include:

- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- `agent_model`
- `available_agent_models`
- `agent_max_steps`
- `agent_bulk_max_concurrent_threads`
- retry policy fields
- image and attachment limit fields
- `agent_base_url`
- `agent_api_key`

Authorization: admin principal only.

Notes:

- identity fields are not mutable through runtime settings
- `user_memory` must be sent as a JSON list of strings; empty list clears the override
- `available_agent_models` must be sent as a JSON list of strings; empty list clears the override
- `agent_base_url` must use `http` or `https` and cannot target localhost or non-public IP literals
- `agent_api_key` cannot be the masked sentinel value `***masked***`
