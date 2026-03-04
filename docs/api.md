# API Reference

Base URL: `http://localhost:8000/api/v1`

## Conventions

- JSON for most endpoints.
- `POST /agent/threads/{thread_id}/messages` and `POST /agent/threads/{thread_id}/messages/stream` use multipart form-data.
- Money values use integer minor units (`amount_minor`, `balance_minor`).
- Currency codes are normalized to uppercase server-side.

## Accounts

## `POST /accounts`

Create an account.

Body:

- `owner_user_id` (optional)
- `name` (required)
- `markdown_body` (optional)
- `currency_code` (required)
- `is_active` (optional, default `true`)

Response: `AccountRead`

## `GET /accounts`

List accounts.

Response: `AccountRead[]`

## `PATCH /accounts/{account_id}`

Partial update.

Body fields (all optional):

- `owner_user_id`
- `name`
- `markdown_body`
- `currency_code`
- `is_active`

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
- `description` (optional)
- `type` (optional)

Response: `TagRead`

Errors: `400` empty name, `409` duplicate.

## `PATCH /tags/{tag_id}`

Update tag name/color/description/type.

Response: `TagRead`

## Taxonomies

## `GET /taxonomies`

List taxonomy definitions.

Response: `TaxonomyRead[]`

Current defaults include:

- `entity_category`
- `tag_type`

## `GET /taxonomies/{taxonomy_key}/terms`

List terms for one taxonomy with usage counts.

Response: `TaxonomyTermRead[]`

## `POST /taxonomies/{taxonomy_key}/terms`

Create or reuse a normalized taxonomy term.

Body:

- `name`
- `parent_term_id` (optional)
- `description` (optional)

Response: `TaxonomyTermRead`

## `PATCH /taxonomies/{taxonomy_key}/terms/{term_id}`

Rename one taxonomy term.

Body:

- `name` (optional)
- `description` (optional)

Response: `TaxonomyTermRead`

## Currencies

## `GET /currencies`

Return built-in + discovered currency catalog.

Response: `CurrencyRead[]`

## Settings

## `GET /settings`

Fetch effective runtime settings (`override -> env default` where applicable) plus override metadata.

Response: `RuntimeSettingsRead`

Response highlights:

- `current_user_name`, optional `user_memory`, `default_currency_code`, `dashboard_currency_code`
- agent runtime fields (`agent_model`, `agent_max_steps`, retry/image limits)
- `agent_base_url` for custom provider endpoint
- `agent_api_key_configured` boolean indicating if a custom API key is set
- `overrides` object with nullable override values for the same runtime fields, including `user_memory`

Behavior:

- `user_memory` is DB-backed only (no environment fallback)
- when `user_memory` is set, it is injected into every agent system prompt as persistent user context
- `agent_api_key` is never returned in responses; use `agent_api_key_configured` to check if a key is set

## `PATCH /settings`

Partially update runtime settings overrides.

Body: any subset of:

- `current_user_name`
- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- `agent_model`
- `agent_max_steps`
- `agent_retry_max_attempts`
- `agent_retry_initial_wait_seconds`
- `agent_retry_max_wait_seconds`
- `agent_retry_backoff_multiplier`
- `agent_max_image_size_bytes`
- `agent_max_images_per_message`
- `agent_base_url` (validated: must use http/https scheme, cannot be localhost/private IPs)
- `agent_api_key` (cannot be the masked sentinel value "***masked***")

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
- `link_type` (`RECURRING` | `SPLIT` | `BUNDLE`)
- `note` (optional)

Response: `LinkRead`

Errors: `400` self-link, `404` not found, `409` duplicate tuple.

## `DELETE /links/{link_id}`

Delete link.

Response: `204`

## Groups

## `GET /groups`

List derived group summaries.

Response: `GroupSummaryRead[]`

`GroupSummaryRead` fields:

- `group_id`
- `entry_count`
- `edge_count`
- `first_occurred_at`
- `last_occurred_at`
- `latest_entry_name`

Behavior:

- groups are connected components derived from active entry links
- single-entry components are omitted (response includes groups with `entry_count >= 2` only)
- endpoint is read-only (no group create/update/delete API)

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

## `DELETE /agent/threads/{thread_id}`

Delete one thread and its persisted timeline artifacts.

Behavior:

- deletes the thread row and cascades deletes for messages, runs, tool calls, change items, and review actions
- removes local uploaded attachment directories under `{data_dir}/agent_uploads/<message_id>/...` for that thread
- rejects delete when any run in the thread is still `running`

Response: `204 No Content`

Errors:

- `404` thread not found
- `409` thread has an active running run

## `GET /agent/threads/{thread_id}`

Fetch timeline-ready thread detail.

Response: `AgentThreadDetailRead` with:

- `thread`
- `messages` (with attachment metadata)
- `runs` (with tool calls + change items + review actions)
- `configured_model_name` (current resolved runtime model from `/settings` override or env default)
- `current_context_tokens` (best-effort prompt size for the selected thread using the current configured model; prefers the newest running run snapshot when available)
- each run also includes nullable context/usage counters:
  - `context_tokens`
  - `input_tokens`
  - `output_tokens`
  - `cache_read_tokens`
  - `cache_write_tokens`
- each run also includes nullable derived USD pricing fields (LiteLLM model-cost mapping):
  - `input_cost_usd`
  - `output_cost_usd`
  - `total_cost_usd`
- each tool call in a run includes both:
  - `output_json` (structured payload)
  - `output_text` (exact model-visible tool result text persisted from runtime)
- each tool call in a run also includes lifecycle metadata:
  - `llm_tool_call_id`
  - `started_at`
  - `completed_at`
  - `status` can now be `queued`, `running`, `ok`, `error`, or `cancelled`
- each run now includes ordered `events[]` rows for replayable run activity history

## `POST /agent/threads/{thread_id}/messages`

Create user message and run agent.

Content type: `multipart/form-data`

Form fields:

- `content` (text, optional if files provided)
- `files` (0..N attachments: images and/or PDFs)

Behavior:

- validates attachment count/size against configured limits
- accepts `image/*` and `application/pdf` uploads
- persists message + attachments
- creates an `agent_runs` row with initial `status=running` and best-effort initial `context_tokens`
- starts bounded tool-calling execution in background
- PDF attachments are parsed to text via PyMuPDF (line-trimmed and internal-whitespace-normalized) before model calls
- when the configured model supports vision, each uploaded PDF page is also sent to the model as an `image_url` part
- resolves provider routing via LiteLLM using configured model name + provider environment credentials
- for prompt-caching-capable models, LiteLLM request payload includes explicit `cache_control_injection_points` anchored to system context + latest user turn (negative index)
- run/tool-call/change-item progress is available via `GET /agent/threads/{thread_id}` and `GET /agent/runs/{run_id}` polling
- proposal tool results include `proposal_id` + `proposal_short_id` so later turns can reference/update pending proposals
- pending proposals can be revised/removed in later turns via internal `update_pending_proposal` / `remove_pending_proposal` tools (thread-scoped, `PENDING_REVIEW` only)

Response: `AgentRunRead`

Usage behavior:

- `context_tokens` is a best-effort snapshot of the run's current model-visible prompt size (message history plus tool schemas), and runtime refreshes it as tool-loop messages are appended
- usage counters are aggregated across all model calls within the run (including tool-calling loops)
- cache counters normalize provider-specific aliases (`cached_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`)
- pricing fields are computed from aggregated input/output tokens using LiteLLM `cost_per_token`
- pricing lookup uses the configured run model name directly
- fields are nullable for providers/responses that do not supply usage metadata
- initial send response can be `running`; poll run/thread endpoints until terminal (`completed` or `failed`)

Errors:

- `400` invalid payload (for example no content/files, unsupported attachment type, limits exceeded)
- `404` thread not found
- `503` provider credentials unavailable for resolved model target

## `POST /agent/threads/{thread_id}/messages/stream`

Create user message and run agent with real-time server-sent events (SSE).

Content type: `multipart/form-data`

Form fields:

- `content` (text, optional if files provided)
- `files` (0..N attachments: images and/or PDFs)

Behavior:

- uses the same validation and persistence rules as `POST /agent/threads/{thread_id}/messages`
- starts run execution in-request and streams incremental agent events
- if client disconnects before terminal event, backend continues the run in background
- thread/run snapshots remain queryable via:
  - `GET /agent/threads/{thread_id}`
  - `GET /agent/runs/{run_id}`

Response content type: `text/event-stream`

Event contract (`event` name and JSON payload `data`):

- `text_delta`
  - `{ "type": "text_delta", "run_id": "<id>", "delta": "<token fragment>" }`
- `run_event`
  - `{ "type": "run_event", "run_id": "<id>", "event": { "id": "<id>", "run_id": "<id>", "sequence_index": 1, "event_type": "run_started|reasoning_update|tool_call_queued|tool_call_started|tool_call_completed|tool_call_failed|tool_call_cancelled|run_completed|run_failed", "source": "model_reasoning|assistant_content|tool_call|null", "message": "<optional message>", "tool_call_id": "<tool-call-id|null>", "created_at": "<iso timestamp>" } }`

Usage behavior:

- usage counters/costs are still persisted on the run record and returned from run/thread snapshot endpoints
- run/thread snapshots now include `runs[].events` plus lifecycle-aware `tool_calls[]` (`llm_tool_call_id`, `started_at`, `completed_at`, expanded status values)
- SSE events stream text plus ordered run activity only; usage totals are not emitted incrementally
- transient stream failures are retried using configured agent retry settings
- retries after partial streamed text suppress already-emitted prefixes to avoid duplicate text

Errors:

- `400` invalid payload (for example no content/files, unsupported attachment type, limits exceeded)
- `404` thread not found
- `503` provider credentials unavailable for resolved model target

## `GET /agent/runs/{run_id}`

Get a run snapshot.

Response: `AgentRunRead`

Returned run payload includes:

- run lifecycle metadata (`status`, `model_name`, `error_text`, `context_tokens`)
- tool calls (including `output_text` + `output_json`) and change items
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
- `create_tag`: creates/reuses normalized tag with type and optional description
- `update_tag`: renames tag and/or updates tag type/description
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

Serve uploaded agent attachment (image or PDF).

Response:

- binary file with stored MIME type

Errors:

- `404` attachment or file missing
