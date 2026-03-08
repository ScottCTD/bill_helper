# Billing Assistant Agent

This document describes the architecture, prompts, tools, and usage workflow of the Bill Helper billing assistant agent.

## Agent UX Quick Path

1. Open the app and navigate to the **Agent** route — this is the AI-native chat workspace.
2. Use **Settings** to configure runtime defaults (currency, model, step limits) before running agent-heavy workflows if needed.
3. Create or select a conversation thread.
4. Send text and optional attachments (images or PDFs) via the composer.
5. Review the timeline as the agent works:
  - User/assistant messages render inline; assistant messages support markdown.
  - In-flight tool-call progress and reasoning updates appear while the run is active.
  - The first tool call in a fresh thread should normally be `rename_thread`, which gives the thread a short topical label immediately.
  - Run/tool context is shown alongside the assistant message.
  - Removable attachment chips (image thumbnails + PDF file chips) appear above the composer before send.
  - Paste (`Cmd/Ctrl+V`) and drag-drop ingestion for image/PDF attachments.
  - `Bulk mode` creates one fresh thread per attached file using only the current textarea prompt; it does not copy the currently selected thread history.
  - Bulk mode launch concurrency comes from runtime settings (`agent_bulk_max_concurrent_threads`), with `4` as the default.
  - Bulk launches stay in the existing thread rail, show immediate running indicators, expose the fresh-thread warning from a hover/focus tooltip, and report started/failed files through transient popup notifications.
  - Composer shortcut: `Cmd+Enter` (or `Ctrl+Enter`) sends the message.
  - Cumulative thread usage bar above the composer: `Context`, `Total input`, `Output`, `Cache read`, `Cache hit rate`, `Total cost`.
  - `Context` is the best-effort current prompt size for the selected thread; `Total input` remains the cumulative billed input usage across completed and in-flight runs.
  - `Total cost` sums backend-derived run totals, so cache-aware prompt pricing is already reflected when providers report cache reads/writes; there are no separate cache-cost fields in the run API.
  - Run-level proposal summary cards with pending counts.
6. Open the thread review modal from the persistent header `Review` button and process proposals:
  - Pending items appear first, with reviewed and failed items kept in a secondary audit section.
  - Entry proposals support structured edit-before-approve with unified payload diff.
  - Group proposals appear in their own `Groups` TOC section. Create/update group proposals edit `name` (and create-only `group_type`), while add-member proposals can edit existing refs plus split role when applicable.
  - Group membership diffs are rendered as relationship updates: the entry snapshot stays stable and only the `group` field changes, with split role shown when relevant.
  - Pending create-proposal refs inside group-member proposals stay locked and render dependency chips with proposal summary plus status; once the dependency proposal is applied, the chip disappears and the resolved group or entry snapshot remains.
  - Tag proposals edit only `name` and `type`; entity proposals edit only `name` and `category`.
  - Review diff rows use friendly field labels/order and human-readable amount values.
  - Non-applied items can be revised after rejection or apply failure, then moved back to pending or approved directly; applied items remain read-only.
  - Use `Approve`, `Reject`, `Move to Pending`, or `Skip` for focused step-through review.
  - Use `Approve All` for deterministic sequential batch apply with saved reviewer edits reused automatically.
  - Use `Reject All` to discard all remaining pending proposals.

## Overview

The agent is a tool-calling LLM (LiteLLM provider routing) with a review-gated mutation model:

- The agent reads data with read tools.
- The agent can rename the current conversation thread with `rename_thread`.
- The agent can publish concise user-visible progress notes with `send_intermediate_update`.
- The agent proposes CRUD changes for entries, groups, tags, and entities.
- The agent does not directly mutate domain tables.
- Domain mutations occur only through human review apply endpoints.

## Core Components


| Component       | File                                                                                                                                                                                                                                                                 | Responsibility                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Runtime         | `backend/services/agent/runtime.py`                                                                                                                                                                                                                                  | Run lifecycle, bounded tool loop, persistence of tool calls and final assistant message                                                                                                                                                                                                                                                                                                                                                                                       |
| Model client    | `backend/services/agent/model_client.py`                                                                                                                                                                                                                             | LiteLLM adapter, tool wiring, retry-enabled model completion, explicit prompt-cache breakpoint injection (system role anchor, boundary before latest assistant+tool batch for tool-loop cache reads, last message for cache writes, second-to-last user for cross-turn reuse) for cache-capable models                                                                                                                                                                                                                                                                                           |
| Prompts         | `backend/services/agent/prompts.py`                                                                                                                                                                                                                                  | Behavioral policy for duplicate checks (including duplicate enrichment via `propose_update_entry`), proposal ordering, explicit new entry/tag/entity specifications, canonical tag/entity normalization (including general tag examples and non-location/default anti-collision rules), error recovery, and current-user context section                                                                                                                                      |
| Message history | `backend/services/agent/message_history.py`                                                                                                                                                                                                                          | Converts thread + attachments to model messages; parses PDF attachments to text via PyMuPDF (line-trimmed and internal-whitespace-normalized); when model vision is supported, includes one rendered image per PDF page; builds current-user account context for system prompt (including account `notes_markdown` from `markdown_body` with truncation safeguards); prepends review outcomes and interruption prefix before current user feedback in the latest user message |
| Tools           | `backend/services/agent/tool_args.py`, `backend/services/agent/tool_handlers_read.py`, `backend/services/agent/tool_handlers_memory.py`, `backend/services/agent/tool_handlers_threads.py`, `backend/services/agent/tool_handlers_propose.py`, `backend/services/agent/entry_references.py`, `backend/services/agent/group_references.py`, `backend/services/agent/proposal_metadata.py`, `backend/services/agent/proposal_patching.py`, `backend/services/agent/tool_runtime.py`, `backend/services/agent/tools.py`, `backend/services/agent/threads.py` | Split tool contract/runtime stack: argument schemas + normalization, read/progress handlers, add-only memory appends, thread-title validation/rename helpers, shared entry/group lookup helpers, proposal metadata mapping, proposal/mutation handlers, patch-map helpers, execution/retry registry, and thin facade |
| Review/apply    | `backend/services/agent/review.py`, `backend/services/agent/change_apply.py`                                                                                                                                                                                         | Approval/rejection, apply handlers for proposed CRUD changes                                                                                                                                                                                                                                                                                                                                                                                                                  |
| API router      | `backend/routers/agent.py`                                                                                                                                                                                                                                           | Threads/runs/send/review/attachment endpoints                                                                                                                                                                                                                                                                                                                                                                                                                                 |


## Runtime Flow

1. User sends message to `POST /api/v1/agent/threads/{thread_id}/messages` (non-streaming) or `POST /api/v1/agent/threads/{thread_id}/messages/stream` (SSE streaming).
2. Backend persists user message/attachments and creates run (`running`).
3. Runtime builds model messages:
  - system prompt (including current-user account context; optional `## Agent Memory` list when `user_memory` is set)
  - current-user account context includes account markdown notes (`notes_markdown` from `markdown_body`) when present
  - thread message history
  - PDF attachments converted to normalized text via PyMuPDF (always)
  - PDF page images appended to multimodal payloads when model vision is supported
  - for the latest user turn only: review outcomes (if any) and interruption prefix (if the previous run was interrupted) prepended before that user feedback text
4. Runtime loops: model call → optional tool calls (including sparse `send_intermediate_update` progress notes) → tool results appended → repeat (bounded by `agent_max_steps`).
5. Runtime persists final assistant message and marks run `completed` or `failed`.
6. For streaming: SSE emits `text_delta` plus persisted `run_event` rows. `run_event` covers run start/finish, `reasoning_update`, and each tool lifecycle transition. `rename_thread` lifecycle events arrive before the run finishes so the client can relabel the thread immediately. `send_intermediate_update` is stored only as a reasoning event (not a fake tool row). On client disconnect mid-stream, the run continues in the background.

## Thread Lifecycle Endpoints

- `GET /api/v1/agent/threads`: list thread summaries
- `POST /api/v1/agent/threads`: create thread shell
- `PATCH /api/v1/agent/threads/{thread_id}`: rename one thread to a normalized 1-5 word title
- `DELETE /api/v1/agent/threads/{thread_id}`: delete one thread history
  - blocked with `409` while the thread has any `running` run
  - cascades DB removal of thread messages/runs/change items/review actions
  - removes persisted upload directories under `{data_dir}/agent_uploads/<message_id>/...`
- `GET /api/v1/agent/threads/{thread_id}`: fetch full thread detail
- `POST /api/v1/agent/threads/{thread_id}/messages`: send message and run agent (non-streaming)
  - used by Bulk mode after creating one fresh thread per attached file
- `POST /api/v1/agent/threads/{thread_id}/messages/stream`: send message and run agent (SSE streaming)
- `GET /api/v1/agent/runs/{run_id}`: fetch run detail
- `POST /api/v1/agent/runs/{run_id}/interrupt`: interrupt a running agent
- `GET /api/v1/agent/attachments/{attachment_id}`: fetch attachment file

## Configuration


| Setting                            | Env                                                           | Default                       | Notes                                                                                           |
| ---------------------------------- | ------------------------------------------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------- |
| `agent_model`                      | `BILL_HELPER_AGENT_MODEL`                                     | `openrouter/qwen/qwen3.5-27b` | Model name; runtime override supported via `/api/v1/settings`                                   |
| `agent_max_steps`                  | `BILL_HELPER_AGENT_MAX_STEPS`                                 | `100`                         | Max tool loop iterations                                                                        |
| `agent_bulk_max_concurrent_threads` | `BILL_HELPER_AGENT_BULK_MAX_CONCURRENT_THREADS`               | `4`                           | Max fresh threads Bulk mode starts concurrently                                                 |
| `current_user_timezone`            | `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` | `America/Toronto`             | User-local date basis for the system-prompt current-date section                                |
| `default_currency_code`            | `BILL_HELPER_DEFAULT_CURRENCY_CODE`                           | `CAD`                         | Fallback for entry proposals missing currency (`/settings` override first, env fallback second) |
| `agent_retry_max_attempts`         | `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS`                        | `3`                           | Model completion retry attempts                                                                 |
| `agent_retry_initial_wait_seconds` | `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS`                | `0.25`                        | Exponential backoff start                                                                       |
| `agent_retry_max_wait_seconds`     | `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS`                    | `4.0`                         | Exponential backoff cap                                                                         |
| `agent_retry_backoff_multiplier`   | `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER`                  | `2.0`                         | Exponential growth factor                                                                       |
| `agent_max_images_per_message`     | `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE`                    | `4`                           | Image/PDF attachment count limit                                                                |
| `agent_max_image_size_bytes`       | `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES`                      | `5242880`                     | Per-attachment size limit for image/PDF uploads                                                 |


Retry behavior notes:

- Both `complete` and `complete_stream` perform a targeted one-shot retry for transient OpenRouter SSL `bad record mac` transport failures surfaced as `litellm.APIError`.
- This targeted retry runs even when `agent_retry_max_attempts` is set to `1`; additional retries still follow the configured tenacity policy.

---

## System Prompt

The agent receives a markdown-structured system prompt at the start of each run. It includes:

- `## Rules` (sectioned policy groups)
- `## Current User Context` (runtime-generated timezone/date bullets, account summaries, and optional account `notes_markdown` from `markdown_body`)
- `## Agent Memory` (optional; when `user_memory` is set via runtime settings as persistent list items)
- rules now include a dedicated `Grouping` section that combines fixed `BUNDLE` / `SPLIT` / `RECURRING` semantics, examples, and the group proposal workflow

```markdown
## Identity
You are an expert in personal finance and accounting. You always call the right tools with the right arguments.

## Current User Context

- User Timezone: America/Toronto
- Current date: 2026-02-10

## Rules
### Tool Discipline
- You may call tools to gather facts and create proposals.
- Before calling any propose_* tool, use read tools to check existing entries/tags/entities.
- Prefer parallel tool calls when tasks are independent.
  If multiple reads/proposals do not depend on each other, call them in the same tool-call batch instead of one by one.
  Use parallel tool calls whenever possible for independent work.
- If you need any tool calls for the task, call send_intermediate_update first
  to briefly describe what you are about to do before calling other tools.
- When transitioning between distinct tool-call batches, use send_intermediate_update
  with a brief progress note so the user can follow your reasoning.
- Use send_intermediate_update sparingly for meaningful transitions; do not call it on every tool step.

### Agent Memory
- Use add_user_memory only when the user clearly asks you to remember/store a preference, rule, or standing hint for future runs.
- add_user_memory is add-only. If the user asks to change or delete stored memory, explain that the agent can only append new memory items.

### Entry Proposal Workflow
- Before proposing any entry, check for duplicates using existing entry data.
- If a duplicate exists, check whether the new input adds complementary information.
  If it does, prefer propose_update_entry for the existing entry instead of propose_create_entry.
- If not duplicate: list existing tags and entities, then propose missing tags/entities first.
- Follow the new entry/tag/entity specifications below when proposing missing records.
- Only after duplicate checks and tag/entity reconciliation, propose entries.

### New Proposal Specifications
#### New Entry Specification
- Ground all proposed fields in explicit source facts. Do not invent missing dates, amounts, counterparties, tags, or locations.
- When assigning an entry name, do not simply copy the original source title. Instead, normalize the name to ensure it is readable, descriptive, and consistent with similar entries.
  - MB-Bill payment - Toronto Hydro-Electric System -> Toronto Hydro Bill Payment
  - FANTUAN DELIVERY BURNABY BC -> Fantuan Delivery
  - OPENAI *CHATGPT SUBSCR -> OpenAI ChatGPT Subscription
  - FARM BOY #29 TORONTO ON -> Farm Boy
- For tools that include a markdown_notes field, write human-readable markdown notes that preserve all relevant
  details from the input. If the content is short, avoid headings. Keep notes clear with line breaks and
  ordered/unordered lists when they improve readability.

#### New Tag Specification
- Normalize new tags to canonical, general descriptors rather than specific names.
- Common tags include grocery, dining, shopping, transportation, reimbursement, income, etc.
- Avoid tags that collide with entities such as credit, loblaw, or heytea.
- Do not include locations in tags unless the user explicitly asks for location-specific tagging.

#### New Entity Specification
- Normalize new entity names to canonical, general forms.
- Prefer normalized names such as IKEA (not IKEA TORONTO DOWNTWON 6423TORONTO), Toronto (not Toronto ON),
  Starbucks (not SBUX), and Apple (not Apple Store #R121).

### Grouping
#### Group Types
- `BUNDLE`: a related set of direct members that should be treated together; the derived graph is fully connected across the direct members.
  Examples: an Uber trip plus a separate Uber tip, or separate payments for the same bill such as two Loblaw payments with the same amount.
- `SPLIT`: one parent side split across child side members; at most one direct member is `PARENT`, parent descendants must be `EXPENSE`, and child descendants must be `INCOME`.
  Example: the user paid for dinner and friends pay them back.
- `RECURRING`: repeated entries of the same `EntryKind` over time; descendant entries must share one kind and the derived graph is a chronological chain.
  Examples: subscriptions, utility bills, or rent.

#### Group Proposal Workflow
- Before mutating an existing group, use list_groups to inspect the current group or find its reusable group_id alias.
- Before proposing group membership changes involving entries, use list_entries to confirm the correct existing entry_id.
- After proposing a new entry, check whether it should join an existing recurring, split, or bundle group. If it should, inspect the likely group with `list_groups` and use `propose_update_group_membership` to add the entry.
- When building a new structure across multiple proposals, use pending create_group and create_entry proposal ids in later propose_update_group_membership calls.
- If a group membership proposal depends on pending create proposals, those dependencies must be approved and applied before the dependent group proposal can be approved.

### Tag Deletion Workflow
- Check whether entries still reference the tag.
- If referenced, surface the impact clearly in the proposal preview so the reviewer can see which entries will lose the tag association.
- `delete_tag` is still allowed while referenced; apply removes the tag and its entry junction rows without deleting entries.

### Pending Proposal Lifecycle
- Use `list_proposals` to inspect proposal history in the current thread before revising,
  removing, or summarizing proposals.
- When the user asks about a specific proposal, prefer `list_proposals` with `proposal_id`
  so you can inspect the exact proposal payload and review history.
- If the user asks to revise an existing pending proposal, prefer update_pending_proposal
  using proposal_id/proposal_short_id instead of creating a duplicate proposal.
- If the user asks to discard/cancel/remove a pending proposal, use remove_pending_proposal
  with the proposal id so it leaves the pending proposal pool.

### Error Handling and Continuation
- If a tool returns an ERROR, decide whether to recover with other tools or ask the user to clarify.
  When updating or deleting an existing entry, prefer the `entry_id` returned by `list_entries`.
  If selector ambiguity is reported, ask the user for clarification before proposing a mutation.
- Reviewed proposal results are prepended in the latest user message before user feedback.
  Use review statuses/comments to improve the next proposal iteration.
  If no explicit user feedback exists, explore missing context and improve proposals proactively.

### Final Response
- End every run with one final assistant message.
- Final message should prioritize a concise direct answer.
  Mention tools only when they materially change the answer or next action.

## Current User Context
...
```

### Message Format

- **System**: Base prompt.
- **User**: Thread messages; content may be plain text or a list of `{ type: "text", text: "..." }` and `{ type: "image_url", image_url: { url: "data:image/...;base64,..." } }`. PDF uploads are converted to markdown text blocks and, when vision is supported, per-page `image_url` items.
- **Assistant**: Thread messages; when tool calls exist, format includes `content` and `tool_calls`.
- **Tool**: `role: "tool"`, `tool_call_id`, `name`, `content` (plain text output from tool execution).

---

## Tools

Tool execution is composed from `backend/services/agent/tool_runtime.py` (registry + execution policy) with handlers in `backend/services/agent/tool_handlers_read.py`, `backend/services/agent/tool_handlers_memory.py`, `backend/services/agent/tool_handlers_threads.py`, and `backend/services/agent/tool_handlers_propose.py`, shared entry/group reference helpers in `backend/services/agent/entry_references.py` and `backend/services/agent/group_references.py`, proposal-domain metadata in `backend/services/agent/proposal_metadata.py`, argument contracts in `backend/services/agent/tool_args.py`, thread-title helpers in `backend/services/agent/threads.py`, and patch-map helpers in `backend/services/agent/proposal_patching.py`. `backend/services/agent/tools.py` is a thin facade that re-exports runtime interfaces. Each tool returns plain-text `content` to the model.

`list_proposals` is the read-only lifecycle inspection tool for proposals in the current thread. Proposal tools (`propose_`*, `update_pending_proposal`, `remove_pending_proposal`) create or mutate `AgentChangeItem` rows while they remain under review. They do not mutate domain data; changes apply only after human approval via approve/reject/reopen endpoints.

### Entries

#### `list_entries` (read)

**Description:** List/query entries by date, date range, `source`, name, from_entity, to_entity, tags, and kind. Use `source` for broad text search across entry name, `from_entity`, and `to_entity`, matching the Entries table search. When source/name/from/to filters are present, exact matches are ranked higher than substring matches. Each returned entry includes an `entry_id` alias (the first 8 characters of the full entry id) that can be reused with `propose_update_entry` and `propose_delete_entry`. This tool is read-only and never mutates data.

**Arguments:**


| Parameter     | Type                 | Required | Default | Constraints                                                       |
| ------------- | -------------------- | -------- | ------- | ----------------------------------------------------------------- |
| `date`        | string (date) | null | no       | null    | ISO date, e.g. `"2026-03-02"`                                     |
| `start_date`  | string (date) | null | no       | null    | ISO date, e.g. `"2026-03-01"`                                     |
| `end_date`    | string (date) | null | no       | null    | ISO date, e.g. `"2026-03-31"`; must be ≥ start_date when both set |
| `source`      | string | null        | no       | null    | broad substring filter across entry name, from_entity, and to_entity |
| `name`        | string | null        | no       | null    | substring filter                                                  |
| `from_entity` | string | null        | no       | null    | substring filter                                                  |
| `to_entity`   | string | null        | no       | null    | substring filter                                                  |
| `tags`        | array of string      | no       | []      | entries must have all tags                                        |
| `kind`        | string | null        | no       | null    | `EXPENSE` or `INCOME`                                             |
| `limit`       | integer              | no       | 10      | ≥1; no upper bound; be cautious with very large values            |


**Expected output (text):**

```
OK
summary: returned N of M matching entries
entries: entry_id=abcd1234 YYYY-MM-DD name amount_minor CURRENCY from=from_entity to=to_entity tags=[...]; ...
```

`N` = count returned (limited by `limit`); `M` = total matching. When N < M, more items exist; increase `limit` or narrow filters to see more. The `entry_id` shown in `list_entries` output is a short alias, not the full stored id.

---

#### `propose_create_entry` (proposal)

**Description:** Create a review-gated proposal to add a new entry. This does not mutate entries immediately; it creates a pending review item only. When `markdown_notes` is provided, keep it human-readable markdown that preserves all relevant input details; for short notes, avoid headings and prefer clear line breaks plus ordered/unordered lists.

**Arguments:**


| Parameter        | Type            | Required | Constraints                                          |
| ---------------- | --------------- | -------- | ---------------------------------------------------- |
| `kind`           | string          | yes      | `EXPENSE` or `INCOME`                                |
| `date`           | string (date)   | yes      | ISO date, e.g. `"2026-03-02"`                        |
| `name`           | string          | yes      | 1–255 chars                                          |
| `amount_minor`   | integer         | yes      | > 0                                                  |
| `from_entity`    | string          | yes      | 1–255 chars                                          |
| `to_entity`      | string          | yes      | 1–255 chars                                          |
| `currency_code`  | string | null   | no       | null; 3 chars; falls back to `default_currency_code` |
| `tags`           | array of string | no       | []                                                   |
| `markdown_notes` | string | null   | no       | null                                                 |


**Expected output:** `OK` with status and preview.

---

#### `propose_update_entry` (proposal)

**Description:** Create a review-gated proposal to update an existing entry. Prefer the `entry_id` alias returned by `list_entries`; selector by date/amount/name/from/to remains available as a fallback. If `entry_id` or selector matches multiple entries, the tool reports ambiguity so the user can clarify. For robustness, the tool also accepts `selector`/`patch` when they arrive as JSON-object strings and normalizes them before validation. When `patch.markdown_notes` is provided, keep it human-readable markdown that preserves all relevant input details; for short notes, avoid headings and prefer clear line breaks plus ordered/unordered lists.

**Arguments:**


| Parameter  | Type          | Required | Constraints                                                                                      |
| ---------- | ------------- | -------- | ------------------------------------------------------------------------------------------------ |
| `entry_id` | string | null | no       | Preferred entry reference; accepts short alias from `list_entries` or full entry id              |
| `selector` | object | null | no       | Fallback reference; exactly one match required (`{"..."}` JSON-object string is also normalized) |
| `patch`    | object        | yes      | At least one field (`{"..."}` JSON-object string is also normalized)                             |


**Selector fields:** `date` (string, ISO date e.g. `"2026-03-02"`), `amount_minor` (integer, > 0), `from_entity` (string), `to_entity` (string), `name` (string).

**Patch fields:** `kind`, `date` (ISO date e.g. `"2026-03-02"`), `name`, `amount_minor`, `currency_code`, `from_entity`, `to_entity`, `tags`, `markdown_notes` (all optional).

**Expected output:** `OK` with status and preview. Returns `ERROR` if no match or if `entry_id`/selector is ambiguous.

**Ambiguity details:**

- If an `entry_id` alias/prefix matches multiple entries, `details` includes the original `entry_id`, `candidate_count`, `candidate_entry_ids` with full entry ids, and `candidates` where each candidate record also uses the full-form `entry_id`.
- If a `selector` matches multiple entries, `details` includes `candidate_count` and `candidates` in the normal public record shape, which means candidate `entry_id` values remain the short public aliases.

---

#### `propose_delete_entry` (proposal)

**Description:** Create a review-gated proposal to delete an existing entry. Prefer the `entry_id` alias returned by `list_entries`; selector by date/amount/name/from/to remains available as a fallback. If `entry_id` or selector matches multiple entries, the tool reports ambiguity so the user can clarify.

**Arguments:**


| Parameter  | Type          | Required | Constraints                                                                         |
| ---------- | ------------- | -------- | ----------------------------------------------------------------------------------- |
| `entry_id` | string | null | no       | Preferred entry reference; accepts short alias from `list_entries` or full entry id |
| `selector` | object | null | no       | Fallback reference; exactly one match required                                      |


**Selector fields:** `date` (string, ISO date e.g. `"2026-03-02"`), `amount_minor` (integer, > 0), `from_entity` (string), `to_entity` (string), `name` (string).

**Expected output:** `OK` with status and preview. Returns `ERROR` if no match or if `entry_id`/selector is ambiguous.

**Ambiguity details:**

- If an `entry_id` alias/prefix matches multiple entries, `details` includes the original `entry_id`, `candidate_count`, `candidate_entry_ids` with full entry ids, and `candidates` where each candidate record also uses the full-form `entry_id`.
- If a `selector` matches multiple entries, `details` includes `candidate_count` and `candidates` in the normal public record shape, which means candidate `entry_id` values remain the short public aliases.

---

### Groups

#### `list_groups` (read)

**Description:** List/query groups by name or `group_type`, or inspect one group in detail with `group_id`. In list mode, each returned row includes a reusable short `group_id` alias. In detail mode, provide only `group_id` and the tool returns the selected group's summary, direct members, and compact derived relationships.

**Arguments:**

| Parameter    | Type          | Required | Default | Constraints                                                |
| ------------ | ------------- | -------- | ------- | ---------------------------------------------------------- |
| `group_id`   | string | null | no       | null    | short alias or full group id; mutually exclusive with all other filters |
| `name`       | string | null | no       | null    | substring filter in list mode                              |
| `group_type` | string | null | no       | null    | `BUNDLE`, `SPLIT`, or `RECURRING` in list mode             |
| `limit`      | integer       | no       | 10      | ≥1; list mode only                                         |

**Expected output (text):**

```
OK
summary: returned N of M matching groups
groups: group_id=abcd1234 Monthly Bills (RECURRING, members=3); ...
```

Detail mode returns one `group` record with summary fields, `direct_members`, and `derived_relationships`.

---

#### `propose_create_group` (proposal)

**Description:** Create a review-gated proposal to add a new named group. Use this before proposing membership changes for a new group.

**Arguments:**

| Parameter    | Type   | Required | Constraints                         |
| ------------ | ------ | -------- | ----------------------------------- |
| `name`       | string | yes      | 1–255 chars, normalized             |
| `group_type` | string | yes      | `BUNDLE`, `SPLIT`, or `RECURRING`   |

**Expected output:** `OK` with status and preview.

---

#### `propose_update_group` (proposal)

**Description:** Create a review-gated proposal to rename an existing group. Prefer the `group_id` alias returned by `list_groups`.

**Arguments:**

| Parameter  | Type   | Required | Constraints                                 |
| ---------- | ------ | -------- | ------------------------------------------- |
| `group_id` | string | yes      | short alias from `list_groups` or full id   |
| `patch`    | object | yes      | rename-only; currently supports `name`      |

**Expected output:** `OK` with status and preview. Returns `ERROR` if the group is missing or ambiguous.

---

#### `propose_delete_group` (proposal)

**Description:** Create a review-gated proposal to delete an existing group. Prefer the `group_id` alias returned by `list_groups`. Apply succeeds only when the group has no direct members and is not attached as a child group.

**Arguments:**

| Parameter  | Type   | Required | Constraints                               |
| ---------- | ------ | -------- | ----------------------------------------- |
| `group_id` | string | yes      | short alias from `list_groups` or full id |

**Expected output:** `OK` with status and preview. Returns `ERROR` if the group is missing or ambiguous.

---

#### `propose_update_group_membership` (proposal)

**Description:** Create a review-gated proposal to add or remove one direct group member. Use `action="add"` or `action="remove"`. `group_ref` points to the parent group and may reference an existing `group_id` or, for adds only, a pending `create_group` proposal in the current thread. `entry_ref` may reference an existing `entry_id` or, for adds only, a pending `create_entry` proposal in the current thread. `member_role` is required for `SPLIT`-group adds and rejected otherwise.

**Arguments:**

| Parameter         | Type              | Required | Constraints |
| ----------------- | ----------------- | -------- | ----------- |
| `action`          | string            | yes      | `add` or `remove` |
| `group_ref`       | object            | yes      | exactly one of `group_id` or `create_group_proposal_id` |
| `entry_ref`       | object | null     | no       | exactly one of `entry_ref` or `child_group_ref` |
| `child_group_ref` | object | null     | no       | exactly one of `entry_ref` or `child_group_ref` |
| `member_role`     | string | null     | no       | `PARENT` or `CHILD`; add-only and only for split groups |

**Expected output:** `OK` with status and preview. Returns `ERROR` for invalid references, duplicate/conflicting pending membership proposals, or invalid group-type rules.

Notes:

- `remove` only supports existing applied `group_id` / `entry_id` / child `group_id` references.
- Existing short ids and pending create-proposal ids are canonicalized into full ids before the proposal is stored, so later review/apply steps use stable references.
- If a pending create proposal referenced by an add-member proposal is later rejected or fails, the member proposal remains pending but cannot be approved until edited or removed.

---

### Tags

#### `list_tags` (read)

**Description:** List/query tags by name and type. Exact matches are ranked higher than substring matches. This tool is read-only and includes tag types.

**Arguments:**


| Parameter | Type          | Required | Default | Constraints                                            |
| --------- | ------------- | -------- | ------- | ------------------------------------------------------ |
| `name`    | string | null | no       | null    | substring filter                                       |
| `type`    | string | null | no       | null    | substring filter                                       |
| `limit`   | integer       | no       | 10      | ≥1; no upper bound; be cautious with very large values |


**Expected output (text):**

```
OK
summary: returned N of M matching tags
tags: name (type or untyped), ...
```

`N` = count returned (limited by `limit`); `M` = total matching.

---

#### `propose_create_tag` (proposal)

**Description:** Create a review-gated proposal to add a new tag. This does not mutate tags immediately; it creates a pending review item only.

**Arguments:**


| Parameter | Type   | Required | Constraints             |
| --------- | ------ | -------- | ----------------------- |
| `name`    | string | yes      | 1–64 chars, normalized  |
| `type`    | string | yes      | 1–100 chars, normalized |


**Expected output:** `OK` with status and preview. Returns `ERROR` if tag already exists.

---

#### `propose_update_tag` (proposal)

**Description:** Create a review-gated proposal to rename a tag and/or update its type. This does not mutate tags immediately; it creates a pending review item only.

**Arguments:**


| Parameter | Type   | Required | Constraints                    |
| --------- | ------ | -------- | ------------------------------ |
| `name`    | string | yes      | 1–64 chars, existing tag name  |
| `patch`   | object | yes      | At least one of `name`, `type` |


**Patch fields:** `name` (string  null), `type` (string  null).

**Expected output:** `OK` with status and preview. Returns `ERROR` if tag not found or target name already exists.

---

#### `propose_delete_tag` (proposal)

**Description:** Create a review-gated proposal to delete a tag. Referenced entries do not block the proposal; impact is reported in the preview.

**Arguments:**


| Parameter | Type   | Required | Constraints                   |
| --------- | ------ | -------- | ----------------------------- |
| `name`    | string | yes      | 1–64 chars, existing tag name |


**Expected output:** `OK` with status and preview, including referenced-entry counts when applicable. Returns `ERROR` only if tag not found.

---

### Entities

#### `list_entities` (read)

**Description:** List/query entities by name and category. Exact matches are ranked higher than substring matches. Account-backed rows are flagged in the returned records and exposed with `category="account"` for lookup purposes. This tool is read-only.

**Arguments:**


| Parameter  | Type          | Required | Default | Constraints                                            |
| ---------- | ------------- | -------- | ------- | ------------------------------------------------------ |
| `name`     | string | null | no       | null    | substring filter                                       |
| `category` | string | null | no       | null    | substring filter                                       |
| `limit`    | integer       | no       | 10      | ≥1; no upper bound; be cautious with very large values |


**Expected output (text):**

```
OK
summary: returned N of M matching entities
entities: name (category or uncategorized); ...
```

`N` = count returned (limited by `limit`); `M` = total matching.

---

#### `propose_create_entity` (proposal)

**Description:** Create a review-gated proposal to add a new entity. This does not mutate entities immediately; it creates a pending review item only.

**Arguments:**


| Parameter  | Type   | Required | Constraints             |
| ---------- | ------ | -------- | ----------------------- |
| `name`     | string | yes      | 1–255 chars, normalized |
| `category` | string | yes      | 1–100 chars, normalized |


**Expected output:** `OK` with status and preview. Returns `ERROR` if entity already exists.

---

#### `propose_update_entity` (proposal)

**Description:** Create a review-gated proposal to rename an entity and/or update its category. This does not mutate entities immediately; it creates a pending review item only.

**Arguments:**


| Parameter | Type   | Required | Constraints                        |
| --------- | ------ | -------- | ---------------------------------- |
| `name`    | string | yes      | 1–255 chars, existing entity name  |
| `patch`   | object | yes      | At least one of `name`, `category` |


**Patch fields:** `name` (string  null), `category` (string  null).

**Expected output:** `OK` with status and preview. Returns `ERROR` if entity not found or target name already exists.

---

#### `propose_delete_entity` (proposal)

**Description:** Create a review-gated proposal to delete a generic entity. Delete behavior detaches nullable entry references while preserving visible labels. Account-backed roots are rejected and must be managed from Accounts.

**Arguments:**


| Parameter | Type   | Required | Constraints                       |
| --------- | ------ | -------- | --------------------------------- |
| `name`    | string | yes      | 1–255 chars, existing entity name |


**Expected output:** `OK` with status and preview for non-account entities. Returns `ERROR` if entity not found or if the target is account-backed.

---

### Progress & Proposal Lifecycle

#### `list_proposals` (read)

**Description:** List proposals in the current thread by proposal type, CRUD action, lifecycle status, or optional `proposal_id`. Use this to inspect pending, rejected, applied, or failed proposals before revising, removing, or explaining proposal history. This tool is read-only.

**Arguments:**


| Parameter         | Type          | Required | Default | Constraints                                                                                             |
| ----------------- | ------------- | -------- | ------- | ------------------------------------------------------------------------------------------------------- |
| `proposal_type`   | string | null | no       | null    | `entry`, `group`, `tag`, or `entity`                                                                    |
| `proposal_status` | string | null | no       | null    | case-insensitive; supports `PENDING_REVIEW`, `APPROVED`, `REJECTED`, `APPLIED`, `APPLY_FAILED`; `pending` also maps to `PENDING_REVIEW`, `failed` to `APPLY_FAILED` |
| `change_action`   | string | null | no       | null    | `create`, `update`, or `delete`                                                                         |
| `proposal_id`     | string | null | no       | null    | full proposal id or unique short-id prefix                                                              |
| `limit`           | integer       | no       | 10      | ≥1; no upper bound; be cautious with very large values                                                  |


**Expected output (text):**

```
OK
summary: returned N of M matching proposals
proposals: proposal_short_id=abcd1234 proposal_id=<uuid> status=REJECTED change_type=create_entity summary=create entity name=... review_actions=[...]; ...
```

Each returned proposal record includes `proposal_id`, `proposal_short_id`, `proposal_type`, `change_action`, `change_type`, `proposal_tool_name`, `status`, `proposal_summary`, `rationale_text`, `payload`, `review_note`, `applied_resource_type`, `applied_resource_id`, timestamps, `run_id`, and `review_actions`.

If `proposal_id` is ambiguous as a short-id prefix, the tool returns `ERROR` with candidate full proposal ids and compact candidate summaries.

---

#### `add_user_memory`

**Description:** Append one or more persistent agent-memory items for future runs. Use only when the user clearly asks the agent to remember a standing preference, rule, or hint. This tool is add-only and must not be used for edits or removals.

**Arguments:**

| Parameter      | Type         | Required | Default | Constraints                                                  |
| -------------- | ------------ | -------- | ------- | ------------------------------------------------------------ |
| `memory_items` | `string[]`   | yes      | —       | 1-20 non-empty items; duplicates are normalized away on save |

**Expected output (text):**

```
OK
summary: added N memory item(s)
added_items: [...]
total_count: N
```

If the user asks to change or delete existing memory, the assistant should explain that only append behavior is supported and should not call this tool.

---

#### `rename_thread`

**Description:** Rename the current thread to a short topical label. Use this right after the first user message in a new thread. After that, only use it when the user explicitly asks for a rename or the conversation topic shifts substantially.

**Arguments:**

| Parameter | Type     | Required | Constraints                          |
| --------- | -------- | -------- | ------------------------------------ |
| `title`   | `string` | yes      | normalized; 1-5 words; max 80 chars |

**Expected output (text):**

```
OK
summary: renamed thread to Budget Review
thread_id: <uuid>
title: Budget Review
```

---

#### `send_intermediate_update`

**Description:** Emit a brief user-visible progress note. If a task needs tool calls, call this first to describe the initial plan before other tools. Then use sparingly between distinct tool-call batches; do not call on every tool step.

**Arguments:**


| Parameter | Type   | Required | Constraints             |
| --------- | ------ | -------- | ----------------------- |
| `message` | string | yes      | 1–400 chars, normalized |


**Expected output (text):**

```
OK
summary: intermediate update shared
message: <update text>
```

---

#### `update_pending_proposal`

**Description:** Update an existing pending proposal in the current thread. This mutates only the proposal payload (`PENDING_REVIEW` item) and does not apply domain data changes.

**Arguments:**


| Parameter     | Type   | Required | Constraints                                             |
| ------------- | ------ | -------- | ------------------------------------------------------- |
| `proposal_id` | string | yes      | full id or unique short-id prefix of a pending proposal |
| `patch_map`   | object | yes      | map of field-path -> new value                          |


**Expected output:** `OK` with updated proposal preview, `proposal_id`, and `proposal_short_id`. Returns `ERROR` for missing/ambiguous/non-pending proposals or invalid patch paths.

---

#### `remove_pending_proposal`

**Description:** Remove an existing pending proposal from the current thread's pending proposal pool. This is for discarding/canceling proposals before review.

**Arguments:**


| Parameter     | Type   | Required | Constraints                                             |
| ------------- | ------ | -------- | ------------------------------------------------------- |
| `proposal_id` | string | yes      | full id or unique short-id prefix of a pending proposal |


**Expected output:** `OK` with removed proposal metadata (`proposal_id`, `proposal_short_id`, `change_type`) and a payload preview. Returns `ERROR` for missing/ambiguous/non-pending proposals.

---

## Tool Output Semantics

Each tool emits model-visible text plus structured `output_json`:

- Success: `status: "OK"`, `summary`, optional `preview`, `item_status`
- Failure: `status: "ERROR"`, `summary`, optional `details`
- Proposal tools additionally return `proposal_id` and `proposal_short_id`.
- `list_proposals` returns `proposals` records with lifecycle status, payload, rationale, and review history for each matching proposal.

For entry ambiguity failures, `details` vary by reference type: ambiguous `entry_id` lookups include full candidate ids, while ambiguous selector lookups include candidates in the normal public record form.

Runtime persists non-intermediate tool calls in `agent_tool_calls` as soon as the model turn resolves, starting in `queued` state before execution begins, and feeds tool output text back to the model for next-step decisions.
When `send_intermediate_update` is called, runtime persists an `agent_run_events.reasoning_update` row and streams it as `run_event`; it no longer creates an `agent_tool_calls` row.
If the model emits assistant text in the same turn as tool calls, runtime persists that text as a `reasoning_update` run event with `source="assistant_content"` instead of a synthetic tool trace.
For continuation after review, `message_history.py` prepends a compact review-results block to the latest user message, then includes user feedback text below it (not as dynamic system prompt text).
Pending proposals from older runs do not block new proposal tools; the model can continue proposing while unresolved items remain pending.
Pending proposals can be inspected, revised, or removed by id in later turns without forcing immediate human review.

## Review Loop and Continuation

**Proposal review endpoints:**

- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`
- `POST /api/v1/agent/change-items/{item_id}/reopen`

`payload_override` is supported for `create_entry`, `update_entry`, `create_group`, `update_group`, `create_group_member`, `create_tag`, `update_tag`, `create_entity`, and `update_entity` across approve, reject, and reopen. Group-member overrides can only adjust existing resource refs or split role; pending proposal refs remain locked in the review UI. Invalid reviewer overrides return `422` and leave the item unchanged. On domain apply failure, item transitions to `APPLY_FAILED` with failure detail in review note.

**Continuation context:** For follow-up turns, `message_history.py` prepends before the latest user feedback message text: (1) a compact review block per item: `tool_name proposal_id=... proposal_short_id=... review_action=... review_item_status=... review_note=... review_override=...`, and (2) when the previous run was interrupted, an interruption note describing the interrupted request. Review context remains outside dynamic system-injected text; account context is intentionally included in system prompt.

**Example review block the agent sees:**

```
Review results from your previous proposals:
1. propose_update_entry proposal_id=ed279837-1911-448b-bdf8-221b55a80a8b proposal_short_id=ed279837 review_action=approve review_item_status=APPLIED review_note=(none)
2. propose_create_tag proposal_id=a1b2c3d4-5678-90ab-cdef-1234567890ab proposal_short_id=a1b2c3d4 review_action=reject review_item_status=REJECTED review_note=Use type recurring instead
3. propose_create_tag proposal_id=b2c3d4e5-6789-01ab-cdef-2345678901bc proposal_short_id=b2c3d4e5 review_action=approve review_item_status=APPLIED review_note=payload_override: name='streaming'; type='media' review_override=name='streaming'; type='media'

User feedback:
Try again with the right type
```

## Apply Semantics (Human Approved)

In `change_apply.py`:

- `create_entry`: create entry directly
- `update_entry`: update uniquely-selected entry by `entry_id` (preferred) or selector
- `delete_entry`: soft-delete uniquely-selected entry
- `create_group`: create a new named typed group owned by the runtime current user
- `update_group`: rename an existing scoped group
- `delete_group`: delete an existing scoped group if it has no direct members and no parent membership
- `create_group_member`: resolve existing or approved pending refs and add one direct member to a group
- `delete_group_member`: resolve direct membership by group + member target and remove it
- `create_tag`: create/reuse normalized tag + assign type
- `update_tag`: rename and/or update type
- `delete_tag`: delete tag, clear taxonomy-backed type assignment, and remove entry junction rows by cascade
- `create_entity`: create/reuse normalized entity + category
- `update_entity`: rename and/or update category (sync denormalized entry labels)
- `delete_entity`: detach `from_entity_id` / `to_entity_id` while preserving denormalized labels, then delete the entity; account-backed roots are rejected

## Affected Files


| File                                              | Purpose                                                              |
| ------------------------------------------------- | -------------------------------------------------------------------- |
| `backend/services/agent/tool_args.py`             | Tool argument schemas and normalization helpers                      |
| `backend/services/agent/tool_handlers_read.py`    | Read/progress tool handlers                                          |
| `backend/services/agent/tool_handlers_memory.py`  | Add-only persistent memory append handler                            |
| `backend/services/agent/tool_handlers_threads.py` | Thread rename tool handler                                           |
| `backend/services/agent/tool_handlers_propose.py` | Proposal/update/remove handlers                                      |
| `backend/services/agent/proposal_patching.py`     | Pending proposal patch-map application helpers                       |
| `backend/services/agent/threads.py`               | Thread-title normalization and rename persistence helpers            |
| `backend/services/agent/tool_runtime.py`          | Tool registry and execution/retry policy                             |
| `backend/services/agent/tools.py`                 | Thin tool facade/re-export layer                                     |
| `backend/services/agent/runtime.py`               | Run orchestration, tool loop                                         |
| `backend/services/agent/model_client.py`          | LiteLLM client with retry                                            |
| `backend/services/agent/prompts.py`               | System prompt                                                        |
| `backend/services/agent/message_history.py`       | LLM message construction and review-result user-message augmentation |
| `backend/services/agent/review.py`                | Approve/reject logic                                                 |
| `backend/services/agent/change_apply.py`          | Apply handlers for approved changes                                  |
| `backend/routers/agent.py`                        | Agent HTTP endpoints                                                 |
