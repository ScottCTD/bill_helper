# Data Model

All data is persisted in SQLite via SQLAlchemy.

## Enum Types

Core:

- `EntryKind`: `EXPENSE`, `INCOME`, `TRANSFER`
- `GroupType`: `BUNDLE`, `SPLIT`, `RECURRING`
- `GroupMemberRole`: `PARENT`, `CHILD`

Legacy note:

- `LinkType` remains in code only to support pre-`0026_entry_groups_v2` migration logic; active group storage no longer persists `entry_links`

Agent:

- `AgentMessageRole`: `user`, `assistant`, `system`
- `AgentRunStatus`: `running`, `completed`, `failed`
- `AgentToolCallStatus`: `ok`, `error`
- `AgentChangeType`:
  - entries: `create_entry`, `update_entry`, `delete_entry`
  - accounts: `create_account`, `update_account`, `delete_account`
  - tags: `create_tag`, `update_tag`, `delete_tag`
  - entities: `create_entity`, `update_entity`, `delete_entity`
  - compatibility: legacy persisted `CREATE_GROUP_MEMBER` rows may still exist in `agent_change_items`; backend hydration accepts them, but current API review payloads omit them because the active client contract no longer includes that proposal type
- `AgentChangeStatus`: `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `APPLIED`, `APPLY_FAILED`
- `AgentReviewActionType`: `approve`, `reject`

## Core Ledger Tables

## `accounts`

- `id` (PK UUID string, FK -> `entities.id`)
- `owner_user_id` (FK -> `users.id`)
- `markdown_body`, `currency_code`, `is_active`
- `created_at`, `updated_at`

Operational rules:

- `accounts` is a subtype table for `entities`; every account is an entity root with the same id.
- Account identity is determined by the presence of a row in `accounts`, not by `entities.category = 'account'`.
- `AccountRead.id` is the only public account identifier; `entity_id` is no longer exposed.

## `account_snapshots`

- `id` (PK)
- `account_id` (FK -> `accounts.id`)
- `snapshot_at`, `balance_minor`, `note`, `created_at`

## `entry_groups`

- `id` (PK)
- `owner_user_id` (FK -> `users.id`)
- `name`
- `group_type`
- `created_at`, `updated_at`

## `users`

- `id` (PK UUID string)
- `name` (unique)
- `password_hash`
- `is_admin` (persisted admin-role gate)
- `created_at`, `updated_at`

## `sessions`

- `id` (PK UUID string)
- `user_id` (FK -> `users.id`)
- `token_hash` (unique SHA-256 digest of the opaque bearer token)
- `created_at`
- `expires_at` (nullable)
- `is_admin_impersonation`

Operational rules:

- password mode never stores raw session tokens in the database
- deleting a user cascades through owned sessions
- logout and admin revocation delete rows from this table

## `filter_groups`

- `id` (PK UUID string)
- `owner_user_id` (FK -> `users.id`)
- `key` (stable internal identifier, unique per owner)
- `name` (user-visible label)
- `description` (nullable)
- `color` (nullable chart/display color)
- `is_default` (built-in vs custom group)
- `position` (owner-local display order)
- `definition_json` (structured include/exclude rule tree)
- `created_at`, `updated_at`

Operational rules:

- filter groups are always principal-owned; admin access does not expose another user's saved groups
- default groups are provisioned lazily per user and persisted on first dashboard/filter-group read
- default groups keep stable `key` values (`day_to_day`, `one_time`, `fixed`, `transfers`, `untagged`) even when their rules are edited
- rule definitions are recursive logical trees over `entry_kind`, tag inclusion/exclusion, and `is_internal_transfer`

## `runtime_settings`

- `id` (PK int)
- `scope` (unique string, current runtime uses `default`)
- nullable override fields:
  - `user_memory`
  - `default_currency_code`
  - `dashboard_currency_code`
  - `agent_model`
  - `available_agent_models` (nullable JSON-serialized ordered list of model identifiers)
  - `entry_tagging_model`
  - `agent_model_display_names` (nullable JSON-serialized object mapping model id → display label for UI)
  - `agent_max_steps`
  - `agent_bulk_max_concurrent_threads`
  - `agent_retry_max_attempts`
  - `agent_retry_initial_wait_seconds`
  - `agent_retry_max_wait_seconds`
  - `agent_retry_backoff_multiplier`
  - `agent_max_image_size_bytes`
  - `agent_max_images_per_message`
  - `agent_base_url` (optional custom provider endpoint, validated to prevent SSRF)
  - `agent_api_key` (optional custom provider API key, never exposed in API responses)
- `created_at`, `updated_at`

Purpose:

- stores optional runtime overrides managed by `/api/v1/settings`
- effective runtime values are resolved as `override -> env default` where applicable
- `user_memory` is an optional DB-only JSON-serialized list of strings used for persistent agent prompt context
- `available_agent_models` is an optional DB-only JSON-serialized ordered list; the resolved API value always includes the effective `agent_model`
  - `agent_model_display_names` is an optional DB-only JSON object of UI labels; the API merges these with built-in labels for known default-catalog model ids and exposes only entries for models in the effective available list
- `vision_capable_agent_models` is not persisted; it is derived at read time from the effective available model list
- identity is not stored here

## `agent_messages`

- `id` (PK UUID string)
- `thread_id` (FK -> `agent_threads.id`)
- `role` (`AgentMessageRole`)
- `content_markdown`
- `attachments_use_ocr` (bool, default `true`; message-level multimodal preference for attached PDFs/images)
- `created_at`

Operational rules:

- `attachments_use_ocr=false` is accepted only when the send-time model supports vision
- later thread replay may still fall back to OCR text when a non-vision model reuses the same history

## `entities`

- `id` (PK UUID string)
- `owner_user_id` (FK -> `users.id`)
- `name` (unique per owner)
- `category` (nullable normalized lowercase, compatibility mirror of taxonomy assignment)
- `created_at`, `updated_at`

Operational rules:

- generic counterparties live only in `entities`
- account-backed entities are the rows whose id also exists in `accounts`
- legacy generic entities may still have `category = 'account'`, but that category no longer grants account semantics

## `entries`

- `id` (PK)
- `account_id` (nullable FK -> `accounts.id`)
- `kind`, `occurred_at`, `name`, `amount_minor`, `currency_code`
- `from_entity_id`, `to_entity_id` (nullable FK -> `entities.id`)
- `owner_user_id` (FK -> `users.id`)
- denormalized labels: `from_entity`, `to_entity`, `owner`
- `markdown_body`
- `is_deleted`, `deleted_at`
- `created_at`, `updated_at`

Deletion semantics:

- `account_id` uses `ON DELETE SET NULL`
- `from_entity_id` / `to_entity_id` use `ON DELETE SET NULL`
- when an entity or account root is deleted, the denormalized `from_entity` / `to_entity` text is intentionally preserved so historical labels remain visible
- API serializers derive `from_entity_missing` / `to_entity_missing` when preserved text remains but the linked entity FK is now `NULL`
- group context is derived from optional membership rows plus parent-chain traversal; there is no persisted `entries.group_id`

## `entry_group_members`

- `id` (PK)
- `group_id` (FK -> `entry_groups.id`)
- `entry_id` (nullable FK -> `entries.id`)
- `child_group_id` (nullable FK -> `entry_groups.id`)
- `member_role` (nullable `GroupMemberRole`)
- `position`
- `created_at`, `updated_at`

Core constraints:

- exactly one of `entry_id` or `child_group_id` must be set
- `entry_id` is globally unique, so an entry can belong to at most one direct group
- `child_group_id` is globally unique, so a child group can belong to at most one parent group
- `(group_id, entry_id)` and `(group_id, child_group_id)` are unique
- `child_group_id != group_id`

Operational rules:

- top-level groups may contain direct entries and/or child groups
- child groups may contain direct entries only
- edges are not persisted; graph topology is derived at read time from `group_type` plus sorted direct membership
- `position` and `created_at` provide deterministic ordering for recurring-group chain derivation
- entry create/update flows may assign or clear one direct group membership inline; split-group assignment also requires a direct member role

## `tags`

- `id` (PK int)
- `owner_user_id` (FK -> `users.id`)
- `name` (unique normalized lowercase per owner)
- `color`
- `description` (nullable free-text note)
- `created_at`

## Taxonomy Tables (`0007_taxonomy_core`)

Taxonomies generalize reusable categorical properties without creating a new table per category type.

## `taxonomies`

- `id` (PK UUID string)
- `owner_user_id` (FK -> `users.id`)
- `key` (unique per owner, e.g. `entity_category`, `tag_type`)
- `applies_to` (subject domain, e.g. `entity`, `tag`)
- `cardinality` (`single` in current defaults)
- `display_name`
- `created_at`, `updated_at`

## `taxonomy_terms`

- `id` (PK UUID string)
- `taxonomy_id` (FK -> `taxonomies.id`)
- `name` (normalized lowercase display value)
- `normalized_name` (unique per taxonomy)
- `parent_term_id` (nullable self-FK for hierarchical terms)
- `metadata_json` (nullable JSON extension slot)
- `created_at`, `updated_at`

Unique constraint:

- `(taxonomy_id, normalized_name)`

Current metadata usage:

- optional term `description` is stored at `metadata_json.description` (used by entity categories/tag types)

## `taxonomy_assignments`

- `id` (PK UUID string)
- `taxonomy_id` (FK -> `taxonomies.id`)
- `term_id` (FK -> `taxonomy_terms.id`)
- `subject_type` (e.g. `entity`, `tag`)
- `subject_id` (string id of referenced subject)
- `position` (reserved for multi-cardinality ordering)
- `created_at`, `updated_at`

Unique constraint:

- `(taxonomy_id, subject_type, subject_id, term_id)`

Current seeded taxonomies:

- `entity_category`
- `tag_type`

## `entry_tags`

- `entry_id` (PK/FK -> `entries.id`)
- `tag_id` (PK/FK -> `tags.id`)

Deletion semantics:

- deleting a tag removes junction rows through `entry_tags.tag_id ON DELETE CASCADE`

## Current Delete Rules

- deleting an account deletes the shared account/entity root, cascades account snapshots, sets `entries.account_id = NULL`, and detaches `from_entity_id` / `to_entity_id` references that pointed at that root while preserving label text
- deleting a generic entity detaches `from_entity_id` / `to_entity_id` and preserves label text
- deleting an account-backed entity through generic entity routes is blocked; account-backed roots are managed through `/accounts`
- soft-deleting an entry removes its direct `entry_group_members` row if one exists
- deleting a group is allowed only when it has no direct members and is not attached as a child group

## Agent Tables (`0006_agent_append_only_core`, `0008_agent_run_usage_metrics`, `0015_add_agent_tool_call_output_text`, `0020_add_agent_message_attachment_original_filename`, `0021_add_agent_run_context_tokens`, `0022_agent_run_events_and_tool_lifecycle`, `0029_add_agent_run_surface`, `0030_add_account_agent_change_types`, `0035_add_user_files_and_agent_workspace`)

## `user_files`

Purpose: canonical registry for durable user-visible uploads, including agent attachment bundles.

Fields:

- `id` (PK UUID string)
- `owner_user_id` (FK -> `users.id`)
- `storage_area` (currently `upload`)
- `source_type` (string origin marker such as `agent_message_attachment`)
- `stored_relative_path` (owner-local relative path under `user_files/{user_id}`)
- `original_filename`
- `display_name`
- `mime_type`
- `size_bytes`
- `sha256` (nullable)
- `created_at`

Operational notes:

- files live under `{data_dir}/user_files/{user_id}/uploads`
- `(owner_user_id, stored_relative_path)` is unique
- deleting a thread removes attachment rows but does not delete canonical file payloads from disk

## `agent_threads`

Purpose: conversation container.

Fields:

- `id` (PK UUID string)
- `owner_user_id` (FK -> `users.id`)
- `title` (nullable)
- `created_at`, `updated_at`

## `agent_messages`

Purpose: timeline messages in a thread.

Fields:

- `id` (PK UUID string)
- `thread_id` (FK -> `agent_threads.id`)
- `role` (`AgentMessageRole`)
- `content_markdown`
- `created_at`

## `agent_message_attachments`

Purpose: message-level linkage from a user message to one canonical `user_files` row.

Fields:

- `id` (PK UUID string)
- `message_id` (FK -> `agent_messages.id`)
- `user_file_id` (FK -> `user_files.id`)
- `created_at`

Operational note:

- new uploads are persisted under `{data_dir}/user_files/{owner_user_id}/uploads/...`
- serializers keep the current attachment API surface by deriving `mime_type`, `original_filename`, and absolute `file_path` from the linked `user_files` row

## `agent_runs`

Purpose: one model execution per user message.

Fields:

- `id` (PK UUID string)
- `thread_id` (FK -> `agent_threads.id`)
- `user_message_id` (FK -> `agent_messages.id`)
- `assistant_message_id` (nullable FK -> `agent_messages.id`)
- `status` (`AgentRunStatus`)
- `model_name`
- `approval_policy` (`default` or `yolo`; `yolo` triggers server-side auto-approval of this run’s pending change items after a successful run completion, subject to the same dependency ordering rules as manual approval)
- `surface` (string execution surface; currently `app` or `telegram`)
- `context_tokens` (nullable int; best-effort prompt-size snapshot for the run's current model-visible context, including tool schemas)
- `input_tokens` (nullable int)
- `output_tokens` (nullable int)
- `cache_read_tokens` (nullable int)
- `cache_write_tokens` (nullable int)
- `error_text`
- `created_at`, `completed_at`

API-derived fields (not persisted in DB columns):

- `terminal_assistant_reply` (latest terminal assistant reply formatted for the requested read surface)
- `input_cost_usd` (nullable float)
- `output_cost_usd` (nullable float)
- `total_cost_usd` (nullable float)
- computed from persisted usage counters via LiteLLM pricing at serialization time
- `input_cost_usd` remains the full prompt-side cost after cache-aware pricing when `cache_read_tokens` or `cache_write_tokens` are present
- `output_cost_usd` remains the completion-side cost
- `total_cost_usd` is the sum of prompt-side and completion-side cost; no separate cache-cost response fields are added
- `model_name` records the explicit message-level selection when a send request overrides the configured default model

## `agent_tool_calls`

Purpose: audit trail for tool usage during a run.

Fields:

- `id` (PK UUID string)
- `run_id` (FK -> `agent_runs.id`)
- `llm_tool_call_id` (nullable provider tool-call id)
- `tool_name`
- `input_json`
- `output_json`
- `output_text` (exact tool result text that was sent to the model)
- `status` (`AgentToolCallStatus`)
- `created_at`
- `started_at` (nullable)
- `completed_at` (nullable)

Operational notes:

- non-intermediate tool rows are created when the model turn resolves, before execution starts
- `send_intermediate_update` is represented only as a `reasoning_update` row in `agent_run_events`, not as an `agent_tool_calls` row

## `agent_run_events`

Purpose: canonical ordered activity timeline for live streaming and historical replay.

Fields:

- `id` (PK UUID string)
- `run_id` (FK -> `agent_runs.id`)
- `sequence_index` (monotonic per run)
- `event_type` (`AgentRunEventType`)
- `source` (nullable `AgentRunEventSource`)
- `message` (nullable)
- `tool_call_id` (nullable FK -> `agent_tool_calls.id`)
- `created_at`

## `agent_change_items`

Purpose: review-gated proposed changes (CRUD proposals across entries/accounts/tags/entities/groups).

Fields:

- `id` (PK UUID string)
- `run_id` (FK -> `agent_runs.id`)
- `change_type` (`AgentChangeType`)
- `payload_json`
- `rationale_text`
- `status` (`AgentChangeStatus`)
- `review_note`
- `applied_resource_type`, `applied_resource_id`
- `created_at`, `updated_at`

## `agent_review_actions`

Purpose: immutable review history per change item.

Fields:

- `id` (PK UUID string)
- `change_item_id` (FK -> `agent_change_items.id`)
- `action` (`AgentReviewActionType`)
- `actor`
- `note`
- `created_at`

## Derived Rules

- `agent_change_items` are created as `PENDING_REVIEW` by proposal creation commands.
- proposal create/list/get responses include proposal ids so later turns can target existing pending items.
- pending proposals remain inspectable while `PENDING_REVIEW` via thread-scoped proposal reads before human review.
- only `PENDING_REVIEW` items can be approved/rejected.
- approving applies exactly one proposed mutation and records review action.
- rejecting records review action and does not create domain resources.
- approving `create_entry` persists an entry directly without an entry-level status column.
- approving `create_account` creates both the account row and its shared entity root (`accounts.id == entities.id`).
- `delete_tag` is allowed only when the tag has no non-deleted entry references.
- `delete_entity` nulls/detaches entity references from entries/accounts before deleting the entity.
- `delete_account` deletes snapshots, clears `entries.account_id`, and detaches account-root entity refs while preserving denormalized labels.
- resolved runtime settings drive current-user attribution defaults, dashboard currency, and agent runtime limits/model selection.

## Currency Catalog (Current)

There is no dedicated `currencies` table.

Currency responses are synthesized from:

- built-in codes in `backend/routers/currencies.py`
- distinct `entries.currency_code` values in non-deleted entries

## Current Constraints

- no auth/tenant scoping for agent or ledger tables
- runtime settings are global to the app instance (single `scope` row in current implementation)
- image files are local filesystem references (not object storage)
- proposal payloads are JSON and schema-evolved by app logic (not DB-level JSON schema constraints)
- category assignments are persisted in taxonomy tables; `entities.category` remains for compatibility and is synchronized by service logic
- historical runs can have null usage counters when model/provider usage metadata is unavailable
- run pricing fields are computed at read time and can be null when usage counters are missing or model pricing is unmapped
