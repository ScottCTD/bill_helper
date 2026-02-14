# Billing Assistant Agent

This document describes the architecture, prompts, and tools of the Bill Helper billing assistant agent.

## Overview

The agent is a tool-calling LLM (OpenRouter via OpenAI-compatible API) with a review-gated mutation model:

- The agent reads data with read tools.
- The agent proposes CRUD changes for entries, tags, and entities.
- The agent does not directly mutate domain tables.
- Domain mutations occur only through human review apply endpoints.

## Core Components

| Component | File | Responsibility |
|-----------|------|----------------|
| Runtime | `backend/services/agent/runtime.py` | Run lifecycle, bounded tool loop, persistence of tool calls and final assistant message |
| Model client | `backend/services/agent/model_client.py` | OpenRouter adapter, tool wiring, retry-enabled model completion |
| Prompts | `backend/services/agent/prompts.py` | Behavioral policy for duplicate checks, proposal ordering, error recovery, and current-user context section |
| Message history | `backend/services/agent/message_history.py` | Converts thread + attachments to model messages; builds current-user account context for system prompt; prepends review outcomes before current user feedback in the latest user message |
| Tools | `backend/services/agent/tools.py` | Read/proposal tool schemas, validation, execution, tool-level retry |
| Review/apply | `backend/services/agent/review.py`, `backend/services/agent/change_apply.py` | Approval/rejection, apply handlers for proposed CRUD changes |
| API router | `backend/routers/agent.py` | Threads/runs/send/review/attachment endpoints |

## Runtime Flow

1. User sends message to `POST /api/v1/agent/threads/{thread_id}/messages`.
2. Backend persists user message/attachments and creates run (`running`).
3. Runtime builds model messages:
   - system prompt (including current-user account context)
   - thread message history
   - for the latest user turn only, review outcomes (if any) prepended before that user feedback text
4. Runtime loops: model call → optional tool calls → tool results appended → repeat (bounded by `agent_max_steps`).
5. Runtime persists final assistant message and marks run `completed` or `failed`.

## Configuration

| Setting | Env | Default | Notes |
|---------|-----|---------|-------|
| `openrouter_api_key` | `OPENROUTER_API_KEY` / `BILL_HELPER_OPENROUTER_API_KEY` | `None` | Required for run execution; can be overridden/cleared via `/api/v1/settings` |
| `openrouter_base_url` | `BILL_HELPER_OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL |
| `agent_model` | `BILL_HELPER_AGENT_MODEL` | `google/gemini-3-flash-preview` | Model name; runtime override supported via `/api/v1/settings` |
| `agent_max_steps` | `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool loop iterations |
| `default_currency_code` | `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Fallback for entry proposals missing currency (`/settings` override first, env fallback second) |
| `agent_retry_max_attempts` | `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` | `3` | Model completion retry attempts |
| `agent_retry_initial_wait_seconds` | `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` | `0.25` | Exponential backoff start |
| `agent_retry_max_wait_seconds` | `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` | `4.0` | Exponential backoff cap |
| `agent_retry_backoff_multiplier` | `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` | `2.0` | Exponential growth factor |
| `agent_max_images_per_message` | `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` | `4` | Attachment count limit |
| `agent_max_image_size_bytes` | `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` | `5242880` | Attachment size limit |

---

## System Prompt

The agent receives a markdown-structured system prompt at the start of each run. It includes:

- `## Current Date (UTC)` (runtime-generated)
- `## Rules` (numbered policy list)
- `## Current User Context` (runtime-generated account summaries)

```markdown
# Bill Helper System Prompt

## Identity
You are the Bill Helper assistant. Follow review-gated mutation policies strictly.

## Current Date (UTC)
2026-02-10

## Rules
1. You may call tools to gather facts and create review-gated proposals.
2. Never claim a proposal is already applied. Proposals require explicit human approval.
3. Before calling any propose_* tool, use read tools to check existing entries/tags/entities.
4. Workflow for entry ingestion:
   0. Before proposing any entry, check for duplicates using existing entry data.
   1. If not duplicate: list existing tags and entities, then propose missing tags/entities first.
   2. Only after duplicate checks and tag/entity reconciliation, propose entries.
5. Do not use domain IDs in proposals; use names and selector fields only.
6. If a tool returns an ERROR, decide whether to recover with other tools or ask the user to clarify.
   If selector ambiguity is reported, ask the user for clarification before proposing a mutation.
7. Reviewed proposal results are prepended in the latest user message before user feedback.
   Use review statuses/comments to improve the next proposal iteration.
   If no explicit user feedback exists, explore missing context and improve proposals proactively.
8. End every run with one final assistant message.
9. Final message should prioritize a concise direct answer.
   Mention tools only when they materially change the answer or next action.
10. Do not ask to run non-existent tools.

## Current User Context
...
```

### Message Format

- **System**: Base prompt.
- **User**: Thread messages; content may be plain text or a list of `{ type: "text", text: "..." }` and `{ type: "image_url", image_url: { url: "data:image/...;base64,..." } }`.
- **Assistant**: Thread messages; when tool calls exist, format includes `content` and `tool_calls`.
- **Tool**: `role: "tool"`, `tool_call_id`, `name`, `content` (plain text output from tool execution).

---

## Tools

All tools are defined in `backend/services/agent/tools.py` and exposed as OpenAI function schemas. Each tool returns plain-text `content` to the model.

### Read Tools

#### `list_entries`

**Description:** List/query entries by date, date range, name, from_entity, to_entity, tags, and kind. When name/from/to filters are present, exact matches are ranked higher than fuzzy matches. This tool is read-only and never mutates data.

**Arguments:**

| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `date` | string (date) \| null | no | null | ISO date |
| `start_date` | string (date) \| null | no | null | ISO date |
| `end_date` | string (date) \| null | no | null | ISO date; must be ≥ start_date when both set |
| `name` | string \| null | no | null | substring filter |
| `from_entity` | string \| null | no | null | substring filter |
| `to_entity` | string \| null | no | null | substring filter |
| `tags` | array of string | no | [] | entries must have all tags |
| `kind` | string \| null | no | null | `EXPENSE` or `INCOME` |
| `limit` | integer | no | 50 | 1–200 |

**Expected output (text):**

```
OK
summary: found N entries
entries: YYYY-MM-DD name amount_minor CURRENCY from=from_entity to=to_entity tags=[...]; ...
```

---

#### `list_tags`

**Description:** List/query tags by name and category. Exact matches are ranked higher than fuzzy matches. This tool is read-only and includes tag categories.

**Arguments:**

| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `name` | string \| null | no | null | substring filter |
| `category` | string \| null | no | null | substring filter |
| `limit` | integer | no | 200 | 1–500 |

**Expected output (text):**

```
OK
summary: found N tags
tags: name (category or uncategorized), ...
```

---

#### `list_entities`

**Description:** List/query entities by name and category. Exact matches are ranked higher than fuzzy matches. Use category='account' when looking for account entities. This tool is read-only.

**Arguments:**

| Parameter | Type | Required | Default | Constraints |
|-----------|------|----------|---------|-------------|
| `name` | string \| null | no | null | substring filter |
| `category` | string \| null | no | null | substring filter |
| `limit` | integer | no | 200 | 1–500 |

**Expected output (text):**

```
OK
summary: found N entities
entities: name (category or uncategorized); ...
```

---

#### `get_dashboard_summary`

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

### Proposal Tools (Review-Gated)

Proposal tools create `AgentChangeItem` rows with status `PENDING_REVIEW`. They do not mutate domain data; changes apply only after human approval via approve/reject endpoints.

#### `propose_create_tag`

**Description:** Create a review-gated proposal to add a new tag. This does not mutate tags immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–64 chars, normalized |
| `category` | string | yes | 1–100 chars, normalized |

**Expected output:** `OK` with status and preview. Returns `ERROR` if tag already exists.

---

#### `propose_update_tag`

**Description:** Create a review-gated proposal to rename a tag and/or update its category. This does not mutate tags immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–64 chars, existing tag name |
| `patch` | object | yes | At least one of `name`, `category` |

**Patch fields:** `name` (string \| null), `category` (string \| null).

**Expected output:** `OK` with status and preview. Returns `ERROR` if tag not found or target name already exists.

---

#### `propose_delete_tag`

**Description:** Create a review-gated proposal to delete a tag. Delete behavior detaches tag references from entries; it does not delete entries.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–64 chars, existing tag name |

**Expected output:** `OK` with status and preview (including impacted entry count). Returns `ERROR` if tag not found.

---

#### `propose_create_entity`

**Description:** Create a review-gated proposal to add a new entity. This does not mutate entities immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–255 chars, normalized |
| `category` | string | yes | 1–100 chars, normalized |

**Expected output:** `OK` with status and preview. Returns `ERROR` if entity already exists.

---

#### `propose_update_entity`

**Description:** Create a review-gated proposal to rename an entity and/or update its category. This does not mutate entities immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–255 chars, existing entity name |
| `patch` | object | yes | At least one of `name`, `category` |

**Patch fields:** `name` (string \| null), `category` (string \| null).

**Expected output:** `OK` with status and preview. Returns `ERROR` if entity not found or target name already exists.

---

#### `propose_delete_entity`

**Description:** Create a review-gated proposal to delete an entity. Delete behavior detaches nullable references from entries/accounts; it does not delete entries/accounts.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `name` | string | yes | 1–255 chars, existing entity name |

**Expected output:** `OK` with status and preview (impacted entries/accounts). Returns `ERROR` if entity not found.

---

#### `propose_create_entry`

**Description:** Create a review-gated proposal to add a new entry. This does not mutate entries immediately; it creates a pending review item only.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `kind` | string | yes | `EXPENSE` or `INCOME` |
| `date` | string (date) | yes | ISO date |
| `name` | string | yes | 1–255 chars |
| `amount_minor` | integer | yes | > 0 |
| `from_entity` | string | yes | 1–255 chars |
| `to_entity` | string | yes | 1–255 chars |
| `currency_code` | string \| null | no | null; 3 chars; falls back to `default_currency_code` |
| `tags` | array of string | no | [] |
| `markdown_notes` | string \| null | no | null |

**Expected output:** `OK` with status and preview.

---

#### `propose_update_entry`

**Description:** Create a review-gated proposal to update an existing entry selected by date/amount/name/from/to. If selector matches multiple entries, the tool reports ambiguity so the user can clarify.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `selector` | object | yes | Exactly one match required |
| `patch` | object | yes | At least one field |

**Selector fields:** `date` (string, ISO), `amount_minor` (integer, > 0), `from_entity` (string), `to_entity` (string), `name` (string).

**Patch fields:** `kind`, `date`, `name`, `amount_minor`, `currency_code`, `from_entity`, `to_entity`, `tags`, `markdown_notes` (all optional).

**Expected output:** `OK` with status and preview. Returns `ERROR` if no match or ambiguous selector.

---

#### `propose_delete_entry`

**Description:** Create a review-gated proposal to delete an existing entry selected by date/amount/name/from/to. If selector matches multiple entries, the tool reports ambiguity so the user can clarify.

**Arguments:**

| Parameter | Type | Required | Constraints |
|-----------|------|----------|-------------|
| `selector` | object | yes | Exactly one match required |

**Selector fields:** `date` (string, ISO), `amount_minor` (integer, > 0), `from_entity` (string), `to_entity` (string), `name` (string).

**Expected output:** `OK` with status and preview. Returns `ERROR` if no match or ambiguous selector.

---

## Tool Output Semantics

Each tool emits model-visible text plus structured `output_json`:

- Success: `status: "OK"`, `summary`, optional `preview`, `item_status`
- Failure: `status: "ERROR"`, `summary`, optional `details`

Runtime persists every tool call in `agent_tool_calls` and feeds tool output text back to the model for next-step decisions.
For continuation after review, `message_history.py` prepends a compact review-results block to the latest user message, then includes user feedback text below it (not as dynamic system prompt text).
Proposal tools are blocked when older pending review items still exist in the same thread; the agent receives an `ERROR` tool output instructing it to ask for review completion first.

## Review Loop and Continuation

**Proposal review endpoints:**

- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`

`payload_override` is supported for `create_entry` and `update_entry`. On apply failure, item transitions to `APPLY_FAILED` with failure detail in review note.

**Continuation context:** For follow-up turns, `message_history.py` prepends reviewed item outcomes (tool name + args summary, status, notes, review action) before the latest user feedback message text. Review context remains outside dynamic system-injected review text; account context is intentionally included in system prompt.

## Apply Semantics (Human Approved)

In `change_apply.py`:

- `create_entry`: create entry directly
- `update_entry`: update uniquely-selected entry by selector
- `delete_entry`: soft-delete uniquely-selected entry
- `create_tag`: create/reuse normalized tag + assign category
- `update_tag`: rename and/or update category
- `delete_tag`: detach from entries then delete tag
- `create_entity`: create/reuse normalized entity + category
- `update_entity`: rename and/or update category (sync denormalized entry labels)
- `delete_entity`: null/detach references from entries/accounts then delete entity

## Affected Files

| File | Purpose |
|------|---------|
| `backend/services/agent/tools.py` | Tool definitions and handlers |
| `backend/services/agent/runtime.py` | Run orchestration, tool loop |
| `backend/services/agent/model_client.py` | OpenRouter client with retry |
| `backend/services/agent/prompts.py` | System prompt |
| `backend/services/agent/message_history.py` | LLM message construction and review-result user-message augmentation |
| `backend/services/agent/review.py` | Approve/reject logic |
| `backend/services/agent/change_apply.py` | Apply handlers for approved changes |
| `backend/routers/agent.py` | Agent HTTP endpoints |
