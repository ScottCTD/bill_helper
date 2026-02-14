# API Reference

Base URL: `http://localhost:8000/api/v1`

## Conventions

- JSON for most endpoints.
- `POST /agent/threads/{thread_id}/messages` uses multipart form-data.
- Money values use integer minor units (`amount_minor`, `balance_minor`).
- Currency codes are normalized to uppercase server-side.

## Accounts

## `POST /accounts`

Create an account.

Body:

- `owner_user_id` (optional)
- `name` (required)
- `institution` (optional)
- `account_type` (optional)
- `currency_code` (required)
- `is_active` (optional, default `true`)

Response: `AccountRead`

## `GET /accounts`

List accounts.

Response: `AccountRead[]`

## `PATCH /accounts/{account_id}`

Partial update.

Response: `AccountRead`

## `POST /accounts/{account_id}/snapshots`

Create balance snapshot.

Body:

- `snapshot_at`
- `balance_minor`
- `note` (optional)

Response: `SnapshotRead`

## `GET /accounts/{account_id}/snapshots`

List snapshots for account.

Response: `SnapshotRead[]`

## `GET /accounts/{account_id}/reconciliation`

Query params:

- `as_of` (optional)

Response: `ReconciliationRead`

## Users

## `GET /users`

List users (marks current configured user).

Response: `UserRead[]`

## `POST /users`

Create user.

Response: `UserRead`

Errors: `400` empty name, `409` duplicate.

## `PATCH /users/{user_id}`

Update user.

Response: `UserRead`

## Entities

## `GET /entities`

List entities with usage counters.

Response: `EntityRead[]`

## `POST /entities`

Create entity (or reuse normalized existing name).

Body:

- `name`
- `category` (optional)

Response: `EntityRead`

## `PATCH /entities/{entity_id}`

Update entity name/category.

Response: `EntityRead`

Behavior:

- category in response is resolved from taxonomy assignment state (reflects taxonomy term renames)

## Tags

## `GET /tags`

List tags with non-deleted entry counts.

Response: `TagRead[]`

## `POST /tags`

Create tag.

Body:

- `name`
- `color` (optional)
- `category` (optional)

Response: `TagRead`

Errors: `400` empty name, `409` duplicate.

## `PATCH /tags/{tag_id}`

Update tag name/color/category.

Response: `TagRead`

## Taxonomies

## `GET /taxonomies`

List taxonomy definitions.

Response: `TaxonomyRead[]`

Current defaults include:

- `entity_category`
- `tag_category`

## `GET /taxonomies/{taxonomy_key}/terms`

List terms for one taxonomy with usage counts.

Response: `TaxonomyTermRead[]`

## `POST /taxonomies/{taxonomy_key}/terms`

Create or reuse a normalized taxonomy term.

Body:

- `name`
- `parent_term_id` (optional)

Response: `TaxonomyTermRead`

## `PATCH /taxonomies/{taxonomy_key}/terms/{term_id}`

Rename one taxonomy term.

Body:

- `name` (optional)

Response: `TaxonomyTermRead`

## Currencies

## `GET /currencies`

Return built-in + discovered currency catalog.

Response: `CurrencyRead[]`

## Settings

## `GET /settings`

Fetch effective runtime settings (`override -> env default`) plus override metadata.

Response: `RuntimeSettingsRead`

Response highlights:

- `current_user_name`, `default_currency_code`, `dashboard_currency_code`
- `openrouter_api_key_source` (`override` | `server_default` | `unset`)
- `openrouter_api_key_configured` (boolean)
- agent runtime fields (`agent_model`, `agent_max_steps`, retry/image limits)
- `overrides` object with nullable override values and `openrouter_api_key_override_set`

## `PATCH /settings`

Partially update runtime settings overrides.

Body: any subset of:

- `current_user_name`
- `default_currency_code`
- `dashboard_currency_code`
- `openrouter_api_key` (empty string or `null` clears override and falls back to server default)
- `openrouter_base_url`
- `agent_model`
- `agent_max_steps`
- `agent_retry_max_attempts`
- `agent_retry_initial_wait_seconds`
- `agent_retry_max_wait_seconds`
- `agent_retry_backoff_multiplier`
- `agent_max_image_size_bytes`
- `agent_max_images_per_message`

Response: `RuntimeSettingsRead`

## Entries

## `POST /entries`

Create entry.

Body:

- `account_id` (optional)
- `kind` (`EXPENSE` | `INCOME`)
- `occurred_at`
- `name`
- `amount_minor` (positive)
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

## `GET /entries`

List entries with filters.

Query params:

- `start_date`, `end_date`
- `kind`, `tag`, `currency`
- `source` (matches `name`/`from_entity`/`to_entity`)
- `account_id`
- `limit` (default `50`, max `200`)
- `offset`

Response: `EntryListResponse`

## `GET /entries/{entry_id}`

Get entry detail with links.

Response: `EntryDetailRead`

## `PATCH /entries/{entry_id}`

Partial update.

Response: `EntryRead`

## `DELETE /entries/{entry_id}`

Soft-delete entry and remove links.

Response: `204`

## Entry Links

## `POST /entries/{entry_id}/links`

Create link.

Body:

- `target_entry_id`
- `link_type` (`RECURRING` | `SPLIT` | `BUNDLE` | `RELATED`)
- `note` (optional)

Response: `LinkRead`

Errors: `400` self-link, `404` not found, `409` duplicate tuple.

## `DELETE /links/{link_id}`

Delete link.

Response: `204`

## Groups

## `GET /groups/{group_id}`

Fetch group graph.

Response: `GroupGraphRead`

## Dashboard

## `GET /dashboard`

Query params:

- `month` (`YYYY-MM`, optional)

Response: `DashboardRead`

Current `DashboardRead` sections:

- `month`
- `currency_code` (resolved dashboard currency setting)
- `kpis`
  - `expense_total_minor`
  - `income_total_minor`
  - `net_total_minor`
  - `daily_expense_total_minor`
  - `non_daily_expense_total_minor`
  - `average_daily_expense_minor`
  - `median_daily_expense_minor`
  - `daily_spending_days`
- `daily_spending[]` (per-day totals for selected month)
  - `date`
  - `expense_total_minor`
  - `daily_expense_minor`
  - `non_daily_expense_minor`
- `monthly_trend[]` (rolling monthly snapshots)
  - `month`
  - `expense_total_minor`
  - `income_total_minor`
  - `daily_expense_minor`
  - `non_daily_expense_minor`
- `spending_by_from[]`, `spending_by_to[]`, `spending_by_tag[]`
  - `label`
  - `total_minor`
  - `share`
- `weekday_spending[]`
  - `weekday`
  - `total_minor`
- `largest_expenses[]`
  - `id`
  - `occurred_at`
  - `name`
  - `to_entity`
  - `amount_minor`
  - `is_daily`
- `projection`
  - `is_current_month`
  - `days_elapsed`
  - `days_remaining`
  - `spent_to_date_minor`
  - `projected_total_minor` (`null` for non-current months)
  - `projected_remaining_minor` (`null` for non-current months)
- `reconciliation[]` (active accounts in the resolved dashboard currency)

Daily classification rule for dashboard analytics:

- expense tagged with `daily` is counted as daily spend
- `non-daily` / `non_daily` / `nondaily` tag overrides and forces non-daily classification

## Agent (Append-Only ReAct)

## `GET /agent/threads`

List threads (most recently updated first).

Response: `AgentThreadSummaryRead[]`

Each row includes:

- thread metadata
- `last_message_preview`
- `pending_change_count`

## `POST /agent/threads`

Create a thread.

Body:

- `title` (optional)

Response: `AgentThreadRead`

## `GET /agent/threads/{thread_id}`

Fetch timeline-ready thread detail.

Response: `AgentThreadDetailRead` with:

- `thread`
- `messages` (with attachment metadata)
- `runs` (with tool calls + change items + review actions)
- `configured_model_name` (current resolved runtime model from `/settings` override or env default)
- each run also includes nullable usage counters:
  - `input_tokens`
  - `output_tokens`
  - `cache_read_tokens`
  - `cache_write_tokens`
- each run also includes nullable derived USD pricing fields (LiteLLM model-cost mapping):
  - `input_cost_usd`
  - `output_cost_usd`
  - `total_cost_usd`

## `POST /agent/threads/{thread_id}/messages`

Create user message and run agent.

Content type: `multipart/form-data`

Form fields:

- `content` (text, optional if files provided)
- `files` (0..N images)

Behavior:

- validates image count/size against configured limits
- persists message + attachments
- creates an `agent_runs` row with initial `status=running`
- starts bounded tool-calling execution in background
- run/tool-call/change-item progress is available via `GET /agent/threads/{thread_id}` and `GET /agent/runs/{run_id}` polling

Response: `AgentRunRead`

Usage behavior:

- usage counters are aggregated across all model calls within the run (including tool-calling loops)
- pricing fields are computed from aggregated input/output tokens using LiteLLM `cost_per_token`
- pricing lookup prefers OpenRouter-prefixed model alias (`openrouter/<model>`) and falls back to raw model name
- fields are nullable for providers/responses that do not supply usage metadata
- initial send response can be `running`; poll run/thread endpoints until terminal (`completed` or `failed`)

Errors:

- `400` invalid payload (for example no content/files, invalid image type, limits exceeded)
- `404` thread not found
- `503` missing API key after runtime resolution (no user override key and no server default key)

## `GET /agent/runs/{run_id}`

Get a run snapshot.

Response: `AgentRunRead`

Returned run payload includes:

- run lifecycle metadata (`status`, `model_name`, `error_text`)
- tool calls and change items
- usage counters (`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`)
- derived pricing fields (`input_cost_usd`, `output_cost_usd`, `total_cost_usd`)

## `POST /agent/runs/{run_id}/interrupt`

Interrupt a currently-running run.

Response: `AgentRunRead`

Behavior:

- if run is `running`, backend marks it `failed` with `error_text = "Run interrupted by user."`
- running worker loop checks persisted run status between model/tool steps and exits without persisting a final assistant message after interruption
- if run is already terminal (`completed`/`failed`), endpoint is a no-op and returns current snapshot

Errors:

- `404` run not found

## `POST /agent/change-items/{item_id}/approve`

Approve and apply one proposal item.

Body:

- `note` (optional)
- `payload_override` (optional; supported for `create_entry` and `update_entry` items)

Response: `AgentChangeItemRead`

State rules:

- allowed only for `PENDING_REVIEW`
- returns `409` if already applied/rejected
- on apply failure, item transitions to `APPLY_FAILED`

Apply behavior:

- `create_entry`: creates entry directly (no entry-level status field)
- `update_entry`: updates one uniquely-selected entry by selector
- `delete_entry`: soft-deletes one uniquely-selected entry by selector
- `create_tag`: creates/reuses normalized tag with category
- `update_tag`: renames tag and/or updates tag category
- `delete_tag`: detaches tag from entries, then deletes tag
- `create_entity`: creates/reuses normalized entity with category
- `update_entity`: renames entity and/or updates entity category
- `delete_entity`: nulls/detaches entity references from entries/accounts, then deletes entity

## `POST /agent/change-items/{item_id}/reject`

Reject one proposal item.

Body:

- `note` (optional)

Response: `AgentChangeItemRead`

State rules:

- allowed only for `PENDING_REVIEW`
- returns `409` if already applied/rejected

## `GET /agent/attachments/{attachment_id}`

Serve uploaded image for timeline rendering.

Response:

- binary file with stored MIME type

Errors:

- `404` attachment or file missing
