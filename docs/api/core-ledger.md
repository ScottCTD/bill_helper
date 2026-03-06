# API Core Ledger

## Accounts

### `POST /accounts`

Create an account.

Body:

- `owner_user_id` (optional)
- `name` (required)
- `markdown_body` (optional)
- `currency_code` (required)
- `is_active` (optional, default `true`)

Response: `AccountRead`

Behavior:

- account id is the shared entity-root id
- response no longer includes `entity_id`

### `GET /accounts`

List accounts. Response: `AccountRead[]`

Behavior: results are principal-scoped by account owner.

### `PATCH /accounts/{account_id}`

Partial update.

Body fields:

- `owner_user_id`
- `name`
- `markdown_body`
- `currency_code`
- `is_active`

Response: `AccountRead`

Behavior: account lookup and update are principal-scoped.

### `DELETE /accounts/{account_id}`

Delete an account root. Response: `204`

Behavior:

- account lookup and delete are principal-scoped
- deletes account snapshots
- sets `entries.account_id = NULL` for linked entries
- clears `from` or `to` account FKs while preserving visible label text

### Snapshot And Reconciliation Endpoints

- `POST /accounts/{account_id}/snapshots` -> `SnapshotRead`
- `GET /accounts/{account_id}/snapshots` -> `SnapshotRead[]`
- `GET /accounts/{account_id}/reconciliation` -> `ReconciliationRead`

## Entries

### `POST /entries`

Create entry.

Body:

- `account_id` (optional)
- `kind` (`EXPENSE` | `INCOME`)
- `occurred_at`
- `name`
- `amount_minor`
- `currency_code`
- `from_entity_id` / `to_entity_id` (optional)
- `owner_user_id` (optional)
- `from_entity` / `to_entity` / `owner` (optional name fallbacks)
- `markdown_body` (optional)
- `tags` (optional string array)

Response: `EntryRead`

Behavior:

- assigns initial entry group
- tag names are normalized to lowercase
- missing tags are auto-created with random colors
- owner defaults to configured current user if omitted
- ownership is scoped to the requesting principal
- read models include `from_entity_missing` / `to_entity_missing` when preserved labels remain after entity/account deletion

### `GET /entries`

List entries with filters.

Query params:

- `start_date`, `end_date`
- `kind`, `tag`, `currency`
- `source`
- `account_id`
- `limit` (default `50`, max `200`)
- `offset`

Response: `EntryListResponse`

Behavior:

- list results are principal-scoped by `owner_user_id`
- each row includes `from_entity_missing` / `to_entity_missing`

### `GET /entries/{entry_id}`

Get entry detail with links. Response: `EntryDetailRead`

Behavior: lookup is principal-scoped and includes missing-entity flags.

### `PATCH /entries/{entry_id}`

Partial update. Response: `EntryRead`

Behavior: update is principal-scoped.

### `DELETE /entries/{entry_id}`

Soft-delete entry and remove links. Response: `204`

Behavior: delete is principal-scoped.

## Entry Links

### `POST /entries/{entry_id}/links`

Create link.

Body:

- `target_entry_id`
- `link_type` (`RECURRING` | `SPLIT` | `BUNDLE`)
- `note` (optional)

Response: `LinkRead`

Errors: `400` self-link, `404` not found, `409` duplicate tuple.

Behavior: both source and target entries must be visible to the requesting principal.

### `DELETE /links/{link_id}`

Delete link. Response: `204`

Behavior: principal access is required to both linked entries.

## Groups

### `GET /groups`

List derived group summaries. Response: `GroupSummaryRead[]`

Behavior:

- groups are connected components derived from active entry links
- single-entry components are omitted
- endpoint is read-only
- responses are principal-scoped to visible entries

### `GET /groups/{group_id}`

Fetch one group graph. Response: `GroupGraphRead`

Behavior: graph lookup is principal-scoped.

## Dashboard

### `GET /dashboard`

Query params:

- `month` (`YYYY-MM`, optional)

Response: `DashboardRead`

Current sections include:

- `month`
- `currency_code`
- `kpis`
- `daily_spending[]`
- `monthly_trend[]`
- `spending_by_from[]`
- `spending_by_to[]`
- `spending_by_tag[]`
- `weekday_spending[]`
- `largest_expenses[]`
- `projection`
- `reconciliation[]`

Behavior:

- daily classification uses `daily` vs `non-daily` tags
- totals and reconciliation are principal-scoped
- analytics exclude internal transfers when both endpoints resolve to account-backed entity roots
