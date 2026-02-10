# Data Model

All data is persisted in SQLite via SQLAlchemy.

## Enum Types

Core:

- `EntryKind`: `EXPENSE`, `INCOME`
- `LinkType`: `RECURRING`, `SPLIT`, `BUNDLE`, `RELATED`

Agent:

- `AgentMessageRole`: `user`, `assistant`, `system`
- `AgentRunStatus`: `running`, `completed`, `failed`
- `AgentToolCallStatus`: `ok`, `error`
- `AgentChangeType`:
  - entries: `create_entry`, `update_entry`, `delete_entry`
  - tags: `create_tag`, `update_tag`, `delete_tag`
  - entities: `create_entity`, `update_entity`, `delete_entity`
- `AgentChangeStatus`: `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `APPLIED`, `APPLY_FAILED`
- `AgentReviewActionType`: `approve`, `reject`

## Core Ledger Tables

## `accounts`

- `id` (PK UUID string)
- `owner_user_id` (nullable FK -> `users.id`)
- `entity_id` (nullable FK -> `entities.id`)
- `name`, `institution`, `account_type`, `currency_code`, `is_active`
- `created_at`, `updated_at`

## `account_snapshots`

- `id` (PK)
- `account_id` (FK -> `accounts.id`)
- `snapshot_at`, `balance_minor`, `note`, `created_at`

## `entry_groups`

- `id` (PK)
- `created_at`, `updated_at`

## `users`

- `id` (PK UUID string)
- `name` (unique)
- `created_at`, `updated_at`

## `entities`

- `id` (PK UUID string)
- `name` (unique)
- `category` (nullable normalized lowercase, compatibility mirror of taxonomy assignment)
- `created_at`, `updated_at`

## `entries`

- `id` (PK)
- `group_id` (FK -> `entry_groups.id`)
- `account_id` (nullable FK -> `accounts.id`)
- `kind`, `occurred_at`, `name`, `amount_minor`, `currency_code`
- `from_entity_id`, `to_entity_id` (nullable FK -> `entities.id`)
- `owner_user_id` (nullable FK -> `users.id`)
- denormalized labels: `from_entity`, `to_entity`, `owner`
- `markdown_body`
- `is_deleted`, `deleted_at`
- `created_at`, `updated_at`

## `entry_links`

- `id` (PK)
- `source_entry_id`, `target_entry_id` (FK -> `entries.id`)
- `link_type`, `note`, `created_at`

Unique constraint:

- `(source_entry_id, target_entry_id, link_type)`

## `tags`

- `id` (PK int)
- `name` (unique normalized lowercase)
- `color`
- `created_at`

## Taxonomy Tables (`0007_taxonomy_core`)

Taxonomies generalize reusable categorical properties without creating a new table per category type.

## `taxonomies`

- `id` (PK UUID string)
- `key` (unique, e.g. `entity_category`, `tag_category`)
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
- `tag_category`

## `entry_tags`

- `entry_id` (PK/FK -> `entries.id`)
- `tag_id` (PK/FK -> `tags.id`)

## Agent Tables (`0006_agent_append_only_core`, `0008_agent_run_usage_metrics`)

## `agent_threads`

Purpose: conversation container.

Fields:

- `id` (PK UUID string)
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

Purpose: uploaded image references tied to user messages.

Fields:

- `id` (PK UUID string)
- `message_id` (FK -> `agent_messages.id`)
- `mime_type`
- `file_path`
- `created_at`

Operational note:

- files are written to `.data/agent_uploads/<message_id>/...`

## `agent_runs`

Purpose: one model execution per user message.

Fields:

- `id` (PK UUID string)
- `thread_id` (FK -> `agent_threads.id`)
- `user_message_id` (FK -> `agent_messages.id`)
- `assistant_message_id` (nullable FK -> `agent_messages.id`)
- `status` (`AgentRunStatus`)
- `model_name`
- `input_tokens` (nullable int)
- `output_tokens` (nullable int)
- `cache_read_tokens` (nullable int)
- `cache_write_tokens` (nullable int)
- `error_text`
- `created_at`, `completed_at`

API-derived fields (not persisted in DB columns):

- `input_cost_usd` (nullable float)
- `output_cost_usd` (nullable float)
- `total_cost_usd` (nullable float)
- computed from `input_tokens` + `output_tokens` via LiteLLM pricing map at serialization time

## `agent_tool_calls`

Purpose: audit trail for tool usage during a run.

Fields:

- `id` (PK UUID string)
- `run_id` (FK -> `agent_runs.id`)
- `tool_name`
- `input_json`
- `output_json`
- `status` (`AgentToolCallStatus`)
- `created_at`

## `agent_change_items`

Purpose: review-gated proposed changes (CRUD proposals across entries/tags/entities).

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

- `agent_change_items` are created as `PENDING_REVIEW` by proposal tools.
- only `PENDING_REVIEW` items can be approved/rejected.
- approving applies exactly one proposed mutation and records review action.
- rejecting records review action and does not create domain resources.
- approving `create_entry` persists an entry directly without an entry-level status column.
- `delete_tag` detaches tag links from entries before deleting the tag.
- `delete_entity` nulls/detaches entity references from entries/accounts before deleting the entity.

## Currency Catalog (Current)

There is no dedicated `currencies` table.

Currency responses are synthesized from:

- built-in codes in `backend/routers/currencies.py`
- distinct `entries.currency_code` values in non-deleted entries

## Current Constraints

- no auth/tenant scoping for agent or ledger tables
- image files are local filesystem references (not object storage)
- proposal payloads are JSON and schema-evolved by app logic (not DB-level JSON schema constraints)
- category assignments are persisted in taxonomy tables; `entities.category` remains for compatibility and is synchronized by service logic
- historical runs can have null usage counters when model/provider usage metadata is unavailable
- run pricing fields are computed at read time and can be null when usage counters are missing or model pricing is unmapped
