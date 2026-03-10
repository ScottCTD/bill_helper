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
- use `/accounts`, not `/entities`, for all new account-like records
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

Errors:

- `422` when no updatable fields are provided

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
- `kind` (`EXPENSE` | `INCOME` | `TRANSFER`)
- `occurred_at`
- `name`
- `amount_minor`
- `currency_code`
- `from_entity_id` / `to_entity_id` (optional)
- `owner_user_id` (optional)
- `from_entity` / `to_entity` / `owner` (optional name fallbacks)
- `direct_group_id` (optional)
- `direct_group_member_role` (`PARENT` | `CHILD`, optional, only valid when assigning into a `SPLIT` group)
- `markdown_body` (optional)
- `tags` (optional string array)

Response: `EntryRead`

Behavior:

- new entries start ungrouped until a group membership is added
- tag names are normalized to lowercase
- missing tags are auto-created with random colors
- owner defaults to configured current user if omitted
- ownership is scoped to the requesting principal
- create flow can assign one direct group membership inline
- embedded `tags` use the lightweight `TagSummaryRead` shape (`id`, `name`, `color`, `description`, `type`) and do not include catalog usage counts
- read models include `from_entity_missing` / `to_entity_missing` when preserved labels remain after entity/account deletion
- read models expose group context through `direct_group` and `group_path`
- read models also expose `direct_group_member_role`

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
- each row includes `direct_group` and `group_path`
- each row's `tags` list uses `TagSummaryRead`, not the `/tags` catalog contract

### `GET /entries/{entry_id}`

Get entry detail. Response: `EntryDetailRead`

Behavior:

- lookup is principal-scoped
- response includes missing-entity flags
- response includes `direct_group` and `group_path`
- response `tags` remain lightweight summaries without `entry_count`
- response no longer includes raw link rows

### `PATCH /entries/{entry_id}`

Partial update. Response: `EntryRead`

Body fields may include any editable entry fields plus:

- `direct_group_id`
- `direct_group_member_role`

Behavior:

- update is principal-scoped
- update can move the entry between groups or clear its direct group
- `direct_group_member_role` is required when assigning into a `SPLIT` group and ignored/rejected for other group types based on validation

### `DELETE /entries/{entry_id}`

Soft-delete entry and remove any direct group membership. Response: `204`

Behavior: delete is principal-scoped.

## Groups

### `POST /groups`

Create a named typed group.

Body:

- `name` (required)
- `group_type` (`BUNDLE` | `SPLIT` | `RECURRING`)

Response: `GroupSummaryRead`

Behavior:

- group ownership is scoped to the requesting principal
- `group_type` is immutable after creation
- empty groups are allowed

### `GET /groups`

List first-class group summaries. Response: `GroupSummaryRead[]`

Behavior:

- responses are principal-scoped
- empty groups are included
- each row includes `parent_group_id`, direct-member counts, descendant entry count, and date range summary

### `GET /groups/{group_id}`

Fetch one group graph. Response: `GroupGraphRead`

Behavior:

- graph lookup is principal-scoped
- nodes are discriminated as direct `ENTRY` or `GROUP` members
- direct `ENTRY` nodes include `amount_minor` and `currency_code` so clients can render currency-aware stats
- edges are derived from `group_type`; they are not stored or edited directly

### `PATCH /groups/{group_id}`

Rename a group.

Body fields:

- `name`

Response: `GroupSummaryRead`

Behavior:

- only rename is supported in v1
- `422` when no updatable fields are provided

### `DELETE /groups/{group_id}`

Delete a group. Response: `204`

Behavior:

- group lookup is principal-scoped
- delete succeeds only when the group has no direct members and is not attached as a child group

### `POST /groups/{group_id}/members`

Add one direct member to a group.

Body:

- `target`
  - `{"target_type":"entry","entry_id":"..."}` for direct entries
  - `{"target_type":"child_group","group_id":"..."}` for child groups
- `member_role` (`PARENT` | `CHILD`) is required for `SPLIT` groups and rejected for other group types

Response: `GroupGraphRead`

Errors:

- `400` invalid payload or domain-rule violation
- `404` target entry/group not visible to the principal
- `409` duplicate membership

### `DELETE /groups/{group_id}/members/{membership_id}`

Remove one direct member. Response: `204`

## Group Rules

- entries can belong to at most one direct group
- child groups can belong to at most one parent group
- nesting depth is exactly one level: top-level groups may contain entries and child groups; child groups may contain entries only
- `BUNDLE` derives a fully connected graph over direct members
- `SPLIT` allows at most one direct `PARENT`; descendant entries under the parent must be `EXPENSE` and descendant entries under children must be `INCOME`
- `RECURRING` requires all descendant entries to share one `EntryKind` and derives a chronological chain from representative dates

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
