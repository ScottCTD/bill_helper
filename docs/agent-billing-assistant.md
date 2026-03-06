# Billing Assistant Agent

This document describes the architecture, prompts, tools, and usage workflow of the Bill Helper billing assistant agent.

## Agent UX Quick Path

1. Open the app and navigate to the **Home** route — this is the AI-native chat workspace.
2. Use **Settings** to configure runtime defaults (currency, model, step limits) before running agent-heavy workflows if needed.
3. Create or select a conversation thread.
4. Send text and optional attachments (images or PDFs) via the composer.
5. Review the timeline as the agent works:
   - User/assistant messages render inline; assistant messages support markdown.
   - In-flight tool-call progress and reasoning updates appear while the run is active.
   - Run/tool context is shown alongside the assistant message.
   - Removable attachment chips (image thumbnails + PDF file chips) appear above the composer before send.
   - Paste (`Cmd/Ctrl+V`) and drag-drop ingestion for image/PDF attachments.
   - Composer shortcut: `Cmd+Enter` (or `Ctrl+Enter`) sends the message.
   - Cumulative thread usage bar above the composer: `Context`, `Total input`, `Output`, `Cache read`, `Cache hit rate`, `Total cost`.
   - `Context` is the best-effort current prompt size for the selected thread; `Total input` remains the cumulative billed input usage across completed and in-flight runs.
   - Run-level proposal summary cards with pending counts.
6. Open the run review modal and process proposals:
   - Entry proposals support JSON edit-before-approve with unified payload diff.
   - Review diff rows use friendly field labels/order and human-readable amount values.
   - Use `Approve & Next` for focused step-through review.
   - Use `Approve All` for deterministic sequential batch apply (with partial-failure summary and jump links).
   - Use `Reject` or `Reject All` to discard proposals.

## Overview

The agent is a tool-calling LLM (LiteLLM provider routing) with a review-gated mutation model:

- The agent reads data with read tools.
- The agent can publish concise user-visible progress notes with `send_intermediate_update`.
- The agent proposes CRUD changes for entries, tags, and entities.
- The agent does not directly mutate domain tables.
- Domain mutations occur only through human review apply endpoints.

## Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Runtime | `backend/services/agent/runtime.py` | Run lifecycle, bounded tool loop, persistence of tool calls and final assistant message |
| Model client | `backend/services/agent/model_client.py` | LiteLLM adapter, tool wiring, retry-enabled model completion, explicit prompt-cache breakpoint injection (system + latest user anchors via negative index) for cache-capable models |
| Prompts | `backend/services/agent/prompts.py` | Behavioral policy for duplicate checks (including duplicate enrichment via `propose_update_entry`), proposal ordering, explicit new entry/tag/entity specifications, canonical tag/entity normalization (including general tag examples and non-location/default anti-collision rules), error recovery, and current-user context section |
| Message history | `backend/services/agent/message_history.py` | Converts thread + attachments to model messages; parses PDF attachments to text via PyMuPDF (line-trimmed and internal-whitespace-normalized); when model vision is supported, includes one rendered image per PDF page; builds current-user account context for system prompt (including account `notes_markdown` from `markdown_body` with truncation safeguards); prepends review outcomes and interruption prefix before current user feedback in the latest user message |
| Tools | `backend/services/agent/tool_args.py`, `backend/services/agent/tool_handlers_read.py`, `backend/services/agent/tool_handlers_propose.py`, `backend/services/agent/proposal_patching.py`, `backend/services/agent/tool_runtime.py`, `backend/services/agent/tools.py` | Split tool contract/runtime stack: argument schemas + normalization, read/progress handlers, proposal/mutation handlers, patch-map helpers, execution/retry registry, and thin facade |
| Review/apply | `backend/services/agent/review.py`, `backend/services/agent/change_apply.py` | Approval/rejection, apply handlers for proposed CRUD changes |
| API router | `backend/routers/agent.py` | Threads/runs/send/review/attachment endpoints |

## Runtime Flow

1. User sends message to `POST /api/v1/agent/threads/{thread_id}/messages` (non-streaming) or `POST /api/v1/agent/threads/{thread_id}/messages/stream` (SSE streaming).
2. Backend persists user message/attachments and creates run (`running`).
3. Runtime builds model messages:
   - system prompt (including current-user account context; optional `## User Memory` when `user_memory` is set)
   - current-user account context includes account markdown notes (`notes_markdown` from `markdown_body`) when present
   - thread message history
   - PDF attachments converted to normalized text via PyMuPDF (always)
   - PDF page images appended to multimodal payloads when model vision is supported
   - for the latest user turn only: review outcomes (if any) and interruption prefix (if the previous run was interrupted) prepended before that user feedback text
4. Runtime loops: model call → optional tool calls (including sparse `send_intermediate_update` progress notes) → tool results appended → repeat (bounded by `agent_max_steps`).
5. Runtime persists final assistant message and marks run `completed` or `failed`.
6. For streaming: SSE emits `text_delta` plus persisted `run_event` rows. `run_event` covers run start/finish, `reasoning_update`, and each tool lifecycle transition. `send_intermediate_update` is stored only as a reasoning event (not a fake tool row). On client disconnect mid-stream, the run continues in the background.

## Thread Lifecycle Endpoints

- `GET /api/v1/agent/threads`: list thread summaries
- `POST /api/v1/agent/threads`: create thread shell
- `DELETE /api/v1/agent/threads/{thread_id}`: delete one thread history
  - blocked with `409` while the thread has any `running` run
  - cascades DB removal of thread messages/runs/change items/review actions
  - removes persisted upload directories under `{data_dir}/agent_uploads/<message_id>/...`
- `GET /api/v1/agent/threads/{thread_id}`: fetch full thread detail
- `POST /api/v1/agent/threads/{thread_id}/messages`: send message and run agent (non-streaming)
- `POST /api/v1/agent/threads/{thread_id}/messages/stream`: send message and run agent (SSE streaming)
- `GET /api/v1/agent/runs/{run_id}`: fetch run detail
- `POST /api/v1/agent/runs/{run_id}/interrupt`: interrupt a running agent
- `GET /api/v1/agent/attachments/{attachment_id}`: fetch attachment file

## Configuration

| Setting | Env | Default | Notes |
|---------|-----|---------|-------|
| `langfuse_public_key` | `LANGFUSE_PUBLIC_KEY` / `BILL_HELPER_LANGFUSE_PUBLIC_KEY` | `None` | Enables LiteLLM Langfuse callbacks when paired with `langfuse_secret_key` |
| `langfuse_secret_key` | `LANGFUSE_SECRET_KEY` / `BILL_HELPER_LANGFUSE_SECRET_KEY` | `None` | Enables LiteLLM Langfuse callbacks when paired with `langfuse_public_key` |
| `langfuse_host` | `LANGFUSE_HOST` / `BILL_HELPER_LANGFUSE_HOST` | `None` | Optional Langfuse host (defaults to Langfuse cloud host if omitted) |
| `agent_model` | `BILL_HELPER_AGENT_MODEL` | `openrouter/qwen/qwen3.5-27b` | Model name; runtime override supported via `/api/v1/settings` |
| `agent_max_steps` | `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool loop iterations |
| `current_user_timezone` | `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` | `America/Toronto` | User-local date basis for the system-prompt current-date section |
| `default_currency_code` | `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Fallback for entry proposals missing currency (`/settings` override first, env fallback second) |
| `agent_retry_max_attempts` | `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` | `3` | Model completion retry attempts |
| `agent_retry_initial_wait_seconds` | `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` | `0.25` | Exponential backoff start |
| `agent_retry_max_wait_seconds` | `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` | `4.0` | Exponential backoff cap |
| `agent_retry_backoff_multiplier` | `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` | `2.0` | Exponential growth factor |
| `agent_max_images_per_message` | `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` | `4` | Image/PDF attachment count limit |
| `agent_max_image_size_bytes` | `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` | `5242880` | Per-attachment size limit for image/PDF uploads |

Retry behavior notes:

- Both `complete` and `complete_stream` perform a targeted one-shot retry for transient OpenRouter SSL `bad record mac` transport failures surfaced as `litellm.APIError`.
- This targeted retry runs even when `agent_retry_max_attempts` is set to `1`; additional retries still follow the configured tenacity policy.

---

## System Prompt

The agent receives a markdown-structured system prompt at the start of each run. It includes:

- `## Current Date (User Timezone: <IANA timezone>)` (runtime-generated; defaults to `America/Toronto`)
- `## Rules` (sectioned policy groups)
- `## Current User Context` (runtime-generated account summaries + optional account `notes_markdown` from `markdown_body`)
- `## User Memory` (optional; when `user_memory` is set via runtime settings—persistent user-provided background and preferences)

```markdown
## Identity
You are an expert in personal finance and accounting. You always call the right tools with the right arguments.

## Current Date (User Timezone: America/Toronto)
2026-02-10

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

### Tag Deletion Workflow
- Check whether entries still reference the tag.
- If referenced, surface the impact clearly in the proposal preview so the reviewer can see which entries will lose the tag association.
- `delete_tag` is still allowed while referenced; apply removes the tag and its entry junction rows without deleting entries.

### Pending Proposal Lifecycle
- If the user asks to revise an existing pending proposal, prefer update_pending_proposal
  using proposal_id/proposal_short_id instead of creating a duplicate proposal.
- If the user asks to discard/cancel/remove a pending proposal, use remove_pending_proposal
  with the proposal id so it leaves the pending proposal pool.

### Error Handling and Continuation
- If a tool returns an ERROR, decide whether to recover with other tools or ask the user to clarify.
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

Tool execution is composed from `backend/services/agent/tool_runtime.py` (registry + execution policy) with handlers in `backend/services/agent/tool_handlers_read.py` and `backend/services/agent/tool_handlers_propose.py`, argument contracts in `backend/services/agent/tool_args.py`, and patch-map helpers in `backend/services/agent/proposal_patching.py`. `backend/services/agent/tools.py` is a thin facade that re-exports runtime interfaces. Each tool returns plain-text `content` to the model.

Proposal tools (`propose_*`, `update_pending_proposal`, `remove_pending_proposal`) create `AgentChangeItem` rows with status `PENDING_REVIEW`. They do not mutate domain data; changes apply only after human approval via approve/reject endpoints.

### Entries

#### `list_entries` (read)

**Description:** List/query entries by date, date range, name, from_entity, to_entity, tags, and kind. When name/from/to filters are present, exact matches are ranked higher than substring matches. This tool is read-only and never mutates data.

**Arguments:**

| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `date` | string (date) \| null | no | null | ISO date, e.g. `"2026-03-02"` |
| `start_date` | string (date) \| null | no | null | ISO date, e.g. `"2026-03-01"` |
| `end_date` | string (date) \| null | no | null | ISO date, e.g. `"2026-03-31"`; must be ≥ start_date when both set |
| `name` | string \| null | no | null | substring filter |
| `from_entity` | string \| null | no | null | substring filter |
| `to_entity` | string \| null | no | null | substring filter |
| `tags` | array of string | no | [] | entries must have all tags |
| `kind` | string \| null | no | null | `EXPENSE` or `INCOME` |
| `limit` | integer | no | 50 | ≥1; no upper bound; be cautious with very large values |

**Expected output (text):**

```
OK
summary: returned N of M matching entries
entries: YYYY-MM-DD name amount_minor CURRENCY from=from_entity to=to_entity tags=[...]; ...
```

`N` = count returned (limited by `limit`); `M` = total matching. When N < M, more items exist; increase `limit` or narrow filters to see more.

---

#### `get_dashboard_summary` (read)

**Description:** Get a compact dashboard snapshot for the current month. Use this for high-level Q&A context. This tool is read-only.

**Arguments:** None (empty object).

**Expected output (text):**

```
OK
summary: dashboard snapshot for YYYY-MM
expenses_by_currency: {"USD": 12345, ...}
incomes_by_currency: {"USD": 50000, ...}
top_tags: tag:USD:1000; ...
```

---

#### `propose_create_entry` (proposal)

**Description:** Create a review-gated proposal to add a new entry. This does not mutate entries immediately; it creates a pending review item only. When `markdown_notes` is provided, keep it human-readable markdown that preserves all relevant input details; for short notes, avoid headings and prefer clear line breaks plus ordered/unordered lists.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `kind` | string | yes | `EXPENSE` or `INCOME` |
| `date` | string (date) | yes | ISO date, e.g. `"2026-03-02"` |
| `name` | string | yes | 1–255 chars |
| `amount_minor` | integer | yes | > 0 |
| `from_entity` | string | yes | 1–255 chars |
| `to_entity` | string | yes | 1–255 chars |
| `currency_code` | string \| null | no | null; 3 chars; falls back to `default_currency_code` |
| `tags` | array of string | no | [] |
| `markdown_notes` | string \| null | no | null |

**Expected output:** `OK` with status and preview.

---

#### `propose_update_entry` (proposal)

**Description:** Create a review-gated proposal to update an existing entry selected by date/amount/name/from/to. If selector matches multiple entries, the tool reports ambiguity so the user can clarify. For robustness, the tool also accepts `selector`/`patch` when they arrive as JSON-object strings and normalizes them before validation. When `patch.markdown_notes` is provided, keep it human-readable markdown that preserves all relevant input details; for short notes, avoid headings and prefer clear line breaks plus ordered/unordered lists.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `selector` | object | yes | Exactly one match required (`{"..."}` JSON-object string is also normalized) |
| `patch` | object | yes | At least one field (`{"..."}` JSON-object string is also normalized) |

**Selector fields:** `date` (string, ISO date e.g. `"2026-03-02"`), `amount_minor` (integer, > 0), `from_entity` (string), `to_entity` (string), `name` (string).

**Patch fields:** `kind`, `date` (ISO date e.g. `"2026-03-02"`), `name`, `amount_minor`, `currency_code`, `from_entity`, `to_entity`, `tags`, `markdown_notes` (all optional).

**Expected output:** `OK` with status and preview. Returns `ERROR` if no match or ambiguous selector.

---

#### `propose_delete_entry` (proposal)

**Description:** Create a review-gated proposal to delete an existing entry selected by date/amount/name/from/to. If selector matches multiple entries, the tool reports ambiguity so the user can clarify.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `selector` | object | yes | Exactly one match required |

**Selector fields:** `date` (string, ISO date e.g. `"2026-03-02"`), `amount_minor` (integer, > 0), `from_entity` (string), `to_entity` (string), `name` (string).

**Expected output:** `OK` with status and preview. Returns `ERROR` if no match or ambiguous selector.

---

### Tags

#### `list_tags` (read)

**Description:** List/query tags by name and type. Exact matches are ranked higher than substring matches. This tool is read-only and includes tag types.

**Arguments:**

| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `name` | string \| null | no | null | substring filter |
| `type` | string \| null | no | null | substring filter |
| `limit` | integer | no | 50 | ≥1; no upper bound; be cautious with very large values |

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

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–64 chars, normalized |
| `type` | string | yes | 1–100 chars, normalized |

**Expected output:** `OK` with status and preview. Returns `ERROR` if tag already exists.

---

#### `propose_update_tag` (proposal)

**Description:** Create a review-gated proposal to rename a tag and/or update its type. This does not mutate tags immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–64 chars, existing tag name |
| `patch` | object | yes | At least one of `name`, `type` |

**Patch fields:** `name` (string \| null), `type` (string \| null).

**Expected output:** `OK` with status and preview. Returns `ERROR` if tag not found or target name already exists.

---

#### `propose_delete_tag` (proposal)

**Description:** Create a review-gated proposal to delete a tag. Referenced entries do not block the proposal; impact is reported in the preview.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–64 chars, existing tag name |

**Expected output:** `OK` with status and preview, including referenced-entry counts when applicable. Returns `ERROR` only if tag not found.

---

### Entities

#### `list_entities` (read)

**Description:** List/query entities by name and category. Exact matches are ranked higher than substring matches. Account-backed rows are flagged in the returned records. This tool is read-only.

**Arguments:**

| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `name` | string \| null | no | null | substring filter |
| `category` | string \| null | no | null | substring filter |
| `limit` | integer | no | 200 | ≥1; no upper bound; be cautious with very large values |

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

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–255 chars, normalized |
| `category` | string | yes | 1–100 chars, normalized |

**Expected output:** `OK` with status and preview. Returns `ERROR` if entity already exists.

---

#### `propose_update_entity` (proposal)

**Description:** Create a review-gated proposal to rename an entity and/or update its category. This does not mutate entities immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–255 chars, existing entity name |
| `patch` | object | yes | At least one of `name`, `category` |

**Patch fields:** `name` (string \| null), `category` (string \| null).

**Expected output:** `OK` with status and preview. Returns `ERROR` if entity not found or target name already exists.

---

#### `propose_delete_entity` (proposal)

**Description:** Create a review-gated proposal to delete a generic entity. Delete behavior detaches nullable entry references while preserving visible labels. Account-backed roots are rejected and must be managed from Accounts.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–255 chars, existing entity name |

**Expected output:** `OK` with status and preview for non-account entities. Returns `ERROR` if entity not found or if the target is account-backed.

---

### Progress & Proposal Lifecycle

#### `send_intermediate_update`

**Description:** Emit a brief user-visible progress note. If a task needs tool calls, call this first to describe the initial plan before other tools. Then use sparingly between distinct tool-call batches; do not call on every tool step.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `message` | string | yes | 1–400 chars, normalized |

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

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `proposal_id` | string | yes | full id or unique short-id prefix of a pending proposal |
| `patch_map` | object | yes | map of field-path -> new value |

**Expected output:** `OK` with updated proposal preview, `proposal_id`, and `proposal_short_id`. Returns `ERROR` for missing/ambiguous/non-pending proposals or invalid patch paths.

---

#### `remove_pending_proposal`

**Description:** Remove an existing pending proposal from the current thread's pending proposal pool. This is for discarding/canceling proposals before review.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `proposal_id` | string | yes | full id or unique short-id prefix of a pending proposal |

**Expected output:** `OK` with removed proposal metadata (`proposal_id`, `proposal_short_id`, `change_type`) and a payload preview. Returns `ERROR` for missing/ambiguous/non-pending proposals.

---

## Tool Output Semantics

Each tool emits model-visible text plus structured `output_json`:

- Success: `status: "OK"`, `summary`, optional `preview`, `item_status`
- Failure: `status: "ERROR"`, `summary`, optional `details`
- Proposal tools additionally return `proposal_id` and `proposal_short_id`.

Runtime persists non-intermediate tool calls in `agent_tool_calls` as soon as the model turn resolves, starting in `queued` state before execution begins, and feeds tool output text back to the model for next-step decisions.
When `send_intermediate_update` is called, runtime persists an `agent_run_events.reasoning_update` row and streams it as `run_event`; it no longer creates an `agent_tool_calls` row.
If the model emits assistant text in the same turn as tool calls, runtime persists that text as a `reasoning_update` run event with `source="assistant_content"` instead of a synthetic tool trace.
For continuation after review, `message_history.py` prepends a compact review-results block to the latest user message, then includes user feedback text below it (not as dynamic system prompt text).
Pending proposals from older runs do not block new proposal tools; the model can continue proposing while unresolved items remain pending.
Pending proposals can be revised or removed by id in later turns without forcing immediate human review.

## Review Loop and Continuation

**Proposal review endpoints:**

- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`

`payload_override` is supported for `create_entry` and `update_entry`. On apply failure, item transitions to `APPLY_FAILED` with failure detail in review note.

**Continuation context:** For follow-up turns, `message_history.py` prepends before the latest user feedback message text: (1) a compact review block per item: `tool_name proposal_id=... proposal_short_id=... review_action=... review_item_status=... review_note=...`, and (2) when the previous run was interrupted, an interruption note describing the interrupted request. Review context remains outside dynamic system-injected text; account context is intentionally included in system prompt.

**Example review block the agent sees:**

```
Review results from your previous proposals:
1. propose_update_entry proposal_id=ed279837-1911-448b-bdf8-221b55a80a8b proposal_short_id=ed279837 review_action=approve review_item_status=APPLIED review_note=(none)
2. propose_create_tag proposal_id=a1b2c3d4-5678-90ab-cdef-1234567890ab proposal_short_id=a1b2c3d4 review_action=reject review_item_status=REJECTED review_note=Use type recurring instead

User feedback:
Try again with the right type
```

## Apply Semantics (Human Approved)

In `change_apply.py`:

- `create_entry`: create entry directly
- `update_entry`: update uniquely-selected entry by selector
- `delete_entry`: soft-delete uniquely-selected entry
- `create_tag`: create/reuse normalized tag + assign type
- `update_tag`: rename and/or update type
- `delete_tag`: delete tag, clear taxonomy-backed type assignment, and remove entry junction rows by cascade
- `create_entity`: create/reuse normalized entity + category
- `update_entity`: rename and/or update category (sync denormalized entry labels)
- `delete_entity`: detach `from_entity_id` / `to_entity_id` while preserving denormalized labels, then delete the entity; account-backed roots are rejected

## Affected Files

| File | Purpose |
|------|---------|
| `backend/services/agent/tool_args.py` | Tool argument schemas and normalization helpers |
| `backend/services/agent/tool_handlers_read.py` | Read/progress tool handlers |
| `backend/services/agent/tool_handlers_propose.py` | Proposal/update/remove handlers |
| `backend/services/agent/proposal_patching.py` | Pending proposal patch-map application helpers |
| `backend/services/agent/tool_runtime.py` | Tool registry and execution/retry policy |
| `backend/services/agent/tools.py` | Thin tool facade/re-export layer |
| `backend/services/agent/runtime.py` | Run orchestration, tool loop |
| `backend/services/agent/model_client.py` | LiteLLM client with retry |
| `backend/services/agent/prompts.py` | System prompt |
| `backend/services/agent/message_history.py` | LLM message construction and review-result user-message augmentation |
| `backend/services/agent/review.py` | Approve/reject logic |
| `backend/services/agent/change_apply.py` | Apply handlers for approved changes |
| `backend/routers/agent.py` | Agent HTTP endpoints |
