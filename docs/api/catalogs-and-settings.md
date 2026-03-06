# API Catalogs And Settings

## Users

### `GET /users`

List users. Response: `UserRead[]`

Behavior:

- admin principal returns all users
- non-admin principal returns only the caller row

### `POST /users`

Create user. Response: `UserRead`

Errors: `400` empty name, `409` duplicate.

Authorization: admin principal only.

### `PATCH /users/{user_id}`

Update user. Response: `UserRead`

Behavior: non-admin principal may update only itself.

## Entities

### `GET /entities`

List entities with usage counters. Response: `EntityRead[]`

Behavior:

- each row includes `is_account`
- account-backed entities are readable but must be managed through `/accounts`

### `POST /entities`

Create entity.

Body:

- `name`
- `category` (optional)

Response: `EntityRead`

Authorization: admin principal only.

Errors: `400` empty name, `409` duplicate normalized name.

### `PATCH /entities/{entity_id}`

Update entity name or category. Response: `EntityRead`

Authorization: admin principal only.

Behavior:

- response category is resolved from taxonomy assignments
- returns `409` for account-backed entities

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
- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- agent runtime fields
- `agent_base_url`
- `agent_api_key_configured`
- `overrides` object with nullable override values

Behavior:

- `user_memory` is DB-backed only
- `agent_api_key` is never returned

### `PATCH /settings`

Partially update runtime settings overrides. Response: `RuntimeSettingsRead`

Updatable fields include:

- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- `agent_model`
- `agent_max_steps`
- retry policy fields
- image and attachment limit fields
- `agent_base_url`
- `agent_api_key`

Authorization: admin principal only.

Notes:

- identity fields are not mutable through runtime settings
- `agent_base_url` must use `http` or `https` and cannot target localhost or non-public IP literals
- `agent_api_key` cannot be the masked sentinel value `***masked***`
