# Completed Plan: AI Agent V1 (Append-Only ReAct)

## Goal

Implement an AI-native sidebar agent that accepts text + image user inputs, can answer questions, can propose append-only data changes, and always requires human review before any database mutation.

This document captures an implementation-ready plan for V1.

## Locked Scope Decisions

1. Write scope is append-only for:
   - Entry creation
   - Tag creation
   - Entity creation
2. Review granularity is per-item (not whole batch).
3. New entries created from approved agent proposals must use `PENDING_REVIEW` status until users explicitly confirm later.
4. The agent is a ReAct-style agent:
   - It may call tools during execution.
   - It must always return a final assistant message at the end of each turn.

## Explicit Non-Goals (V1)

1. No direct update/delete tools for entries/tags/entities.
2. No bank/email ingestion automation.
3. No background autonomous runs without user prompt.
4. No model/provider abstraction beyond OpenRouter + DeepSeek default (configurable by env).

## Architecture Summary

### Runtime

1. Backend-hosted LangGraph ReAct workflow.
2. LangChain model client configured to call OpenRouter.
3. Default model identifier: `openrouter/qwen/qwen3.5-27b` (configurable).
4. Graph terminates only when a final assistant message is produced.

### Tooling Strategy

1. Read tools (safe):
   - Search/list entries
   - List tags
   - List entities
   - List accounts
   - Read dashboard summaries
2. Write tools (proposal only):
   - `propose_create_entry`
   - `propose_create_tag`
   - `propose_create_entity`
3. Apply of proposals is never a tool call from the agent; it is a dedicated reviewed backend action.

## Tool Specifications (Docstring + Arguments)

Use these as the canonical V1 LangChain/LangGraph tool contracts.

### Shared Tool Contract Rules

1. All tools return a formatted `str` to the model (not JSON objects).
2. All tool args must be validated by Pydantic models before execution.
3. Write tools never mutate domain tables directly; they only create `agent_change_items` in `PENDING_REVIEW`.
4. Structured tool outputs should still be persisted server-side in `agent_tool_calls.output_json` for UI/history/audit.
5. Tool output strings should stay compact and consistent:
   - first line: status (`OK` or `ERROR`)
   - second line: short summary
   - optional lines: compact key/value details

### Read Tool: `search_entries`

Docstring text:

```text
Search entries by free-text query across name/from/to fields.
Use this for factual Q&A and duplicate checks before proposing new entries.
This tool is read-only and never mutates data.
```

Arguments:

1. `query: str` (required)
2. `limit: int = 20` (min `1`; no upper bound)

Return format (string):

1. `OK`
2. `summary: found <n> entries for query "<query>"`
3. `entries: <compact list of top results with id/date/name/amount/currency/status>`

### Read Tool: `list_entries`

Docstring text:

```text
List entries using a basic date-range filter.
Use this when the user asks for recent activity, period summaries, or timeline inspection.
This tool is read-only and never mutates data.
```

Arguments:

1. `start_date: date | None = None`
2. `end_date: date | None = None`
3. `limit: int = 50` (min `1`; no upper bound)

Behavior:

1. If both dates are omitted, return most recent entries.
2. If one date is omitted, apply one-sided range filtering.
3. Sort by `occurred_at DESC`, then `created_at DESC`.

Return format (string):

1. `OK`
2. `summary: found <n> entries in date range`
3. `entries: <compact list of top results with id/date/name/amount/currency/status>`

### Read Tool: `list_tags`

Docstring text:

```text
List tags for grounding and reuse.
Prefer an existing tag before proposing a new one.
This tool is read-only.
```

Arguments:

1. `query: str | None = None` (optional tag name contains filter)

Return format (string):

1. `OK`
2. `summary: found <n> tags`
3. `tags: <compact list of tag names>`

### Read Tool: `list_entities`

Docstring text:

```text
List entities for grounding and reuse.
Prefer an existing entity before proposing a new one.
This tool is read-only.
```

Arguments:

1. `query: str | None = None` (optional entity name contains filter)

Return format (string):

1. `OK`
2. `summary: found <n> entities`
3. `entities: <compact list of entity id/name/category>`

### Read Tool: `list_accounts`

Docstring text:

```text
List active accounts for entry context.
This tool is read-only.
```

Arguments:

1. No arguments.

Return format (string):

1. `OK`
2. `summary: found <n> active accounts`
3. `accounts: <compact list of account id/name/currency>`

### Proposal Tool: `propose_create_tag`

Docstring text:

```text
Create a review-gated proposal to add a new tag.
This does not create the tag immediately; it creates a pending review item only.
Use only when no suitable existing tag is found.
```

Arguments:

1. `name: str` (required, non-empty)
2. `color: str | None = None` (optional; if omitted, existing backend random-color behavior applies at apply-time)
3. `rationale: str` (required, concise human-readable explanation)

Return format (string):

1. `OK`
2. `summary: proposed tag creation`
3. `change_item_id: <id>`
4. `status: PENDING_REVIEW`
5. `preview: <name/color>`

### Proposal Tool: `propose_create_entity`

Docstring text:

```text
Create a review-gated proposal to add a new entity.
This does not create the entity immediately; it creates a pending review item only.
Use only when no suitable existing entity is found.
```

Arguments:

1. `name: str` (required, non-empty)
2. `category: str | None = None` (optional normalized lowercase)
3. `rationale: str` (required, concise human-readable explanation)

Return format (string):

1. `OK`
2. `summary: proposed entity creation`
3. `change_item_id: <id>`
4. `status: PENDING_REVIEW`
5. `preview: <name/category>`

### Proposal Tool: `propose_create_entry`

Docstring text:

```text
Create a review-gated proposal to add a new ledger entry.
This does not create the entry immediately; it creates a pending review item only.
Use existing entities/tags/accounts when available and include rationale for the proposed fields.
```

Arguments:

1. `kind: Literal["EXPENSE","INCOME"]` (required)
2. `occurred_at: date` (required)
3. `name: str` (required, non-empty)
4. `amount_minor: int` (required, must be `> 0`)
5. `currency_code: str` (required, uppercase 3-char code)
6. `account_id: str | None = None`
7. `from_entity_id: str | None = None`
8. `to_entity_id: str | None = None`
9. `from_entity: str | None = None` (name fallback when id unknown)
10. `to_entity: str | None = None` (name fallback when id unknown)
11. `owner_user_id: str | None = None`
12. `owner: str | None = None` (name fallback when id unknown)
13. `tags: list[str] = []`
14. `markdown_body: str | None = None`
15. `rationale: str` (required, concise human-readable explanation)
16. `duplicate_check_note: str | None = None` (optional explanation of what was checked)

Return format (string):

1. `OK`
2. `summary: proposed entry creation`
3. `change_item_id: <id>`
4. `status: PENDING_REVIEW`
5. `preview: <date/kind/name/amount/currency/tags>`

### Agent Tool Invocation Policy (V1)

1. Before any `propose_*` call, the agent should call relevant read tools to ground values and avoid duplicates.
2. The agent may make multiple tool calls per run, but must end with one final assistant message.
3. A final assistant message must summarize:
   - direct answer to user ask
   - which tools were used (high level)
   - which change items are awaiting review
4. If tool execution fails, the agent should recover if possible and still produce a final assistant message.

### Safety Boundary

1. Agent writes to proposal tables only.
2. Core tables (`entries`, `tags`, `entities`) mutate only from explicit review endpoints.
3. Each review apply action is transactional and audited.

## Data Model Additions (Alembic Migration)

Add these tables:

1. `agent_threads`
   - `id`
   - `title` (nullable, generated summary)
   - `created_at`, `updated_at`
2. `agent_messages`
   - `id`
   - `thread_id` (FK)
   - `role` (`user` | `assistant` | `system`)
   - `content_markdown`
   - `created_at`
3. `agent_message_attachments`
   - `id`
   - `message_id` (FK)
   - `mime_type`
   - `file_path`
   - `created_at`
4. `agent_runs`
   - `id`
   - `thread_id` (FK)
   - `user_message_id` (FK)
   - `assistant_message_id` (FK nullable until run completes)
   - `status` (`running` | `completed` | `failed`)
   - `model_name`
   - `error_text` (nullable)
   - `created_at`, `completed_at`
5. `agent_tool_calls`
   - `id`
   - `run_id` (FK)
   - `tool_name`
   - `input_json`
   - `output_json` (or summarized output)
   - `status` (`ok` | `error`)
   - `created_at`
6. `agent_change_items`
   - `id`
   - `run_id` (FK)
   - `change_type` (`create_entry` | `create_tag` | `create_entity`)
   - `payload_json`
   - `rationale_text`
   - `status` (`PENDING_REVIEW` | `APPROVED` | `REJECTED` | `APPLIED` | `APPLY_FAILED`)
   - `review_note` (nullable)
   - `applied_resource_type` (nullable)
   - `applied_resource_id` (nullable)
   - `created_at`, `updated_at`
7. `agent_review_actions`
   - `id`
   - `change_item_id` (FK)
   - `action` (`approve` | `reject`)
   - `actor` (string, current user name for now)
   - `note` (nullable)
   - `created_at`

Notes:

1. Keep all proposal payloads as JSON for auditability and forward compatibility.
2. Store attachment files under a dedicated path like `.data/agent_uploads`.

## Backend Implementation TODO

## 1) Configuration

Files:

- `backend/config.py`

Tasks:

1. Add env settings:
   - `BILL_HELPER_OPENROUTER_API_KEY`
   - `BILL_HELPER_OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`)
   - `BILL_HELPER_AGENT_MODEL` (default `openrouter/qwen/qwen3.5-27b`)
   - `BILL_HELPER_AGENT_MAX_STEPS` (reasonable default like `100`)
2. Add optional limits:
   - max image size
   - max images per message

Acceptance:

1. App boots with defaults when API key is unset (agent endpoints can fail with clear 503/400).
2. Env overrides are visible in runtime behavior.

## 2) Models + Schemas

Files:

- `backend/models.py`
- `backend/schemas.py`
- `alembic/versions/<new_revision>.py`

Tasks:

1. Add ORM models for all new agent tables.
2. Add Pydantic request/response schemas for:
   - Thread list/detail
   - Send message (text + files metadata)
   - Tool call history
   - Change item review actions

Acceptance:

1. `uv run alembic upgrade head` creates tables successfully.
2. Schema serialization covers thread timeline + review queue use cases.

## 3) Agent Service Layer

Files:

- `backend/services/agent/runtime.py`
- `backend/services/agent/tools.py`
- `backend/services/agent/review.py`
- `backend/services/agent/serializers.py`
- `backend/services/agent/__init__.py`

Tasks:

1. Build LangGraph ReAct runner:
   - message context load
   - tool calling
   - final message enforcement
2. Implement read tools (query existing domain tables).
3. Implement proposal tools:
   - Validate payload shape.
   - Persist `agent_change_items` with `PENDING_REVIEW`.
4. Persist tool call logs (`agent_tool_calls`) per run.
5. Review/apply service:
   - approve item -> validate payload -> apply create action -> mark `APPLIED`
   - reject item -> mark `REJECTED`
6. Use existing domain logic when applying:
   - Entry creation path should preserve current normalization and owner defaults.
   - Tag/entity creation should keep existing uniqueness/normalization behavior.

Acceptance:

1. Agent run with only Q&A produces zero change items and one final assistant message.
2. Agent run with append intent produces one or more `PENDING_REVIEW` change items.
3. Approved item writes to domain table exactly once (idempotent against duplicate apply request).
4. Tool calls are visible in persisted history.

## 4) API Endpoints

Files:

- `backend/routers/agent.py`
- `backend/main.py` (router registration)
- `backend/schemas.py`

Endpoints:

1. `GET /api/v1/agent/threads`
2. `POST /api/v1/agent/threads`
3. `GET /api/v1/agent/threads/{thread_id}`
4. `POST /api/v1/agent/threads/{thread_id}/messages`
   - Supports text + image attachments
   - Triggers run and returns run snapshot
5. `GET /api/v1/agent/runs/{run_id}`
6. `POST /api/v1/agent/change-items/{item_id}/approve`
7. `POST /api/v1/agent/change-items/{item_id}/reject`

Behavior rules:

1. Per-item review only.
2. Approval is blocked unless item is `PENDING_REVIEW`.
3. Re-approval on already applied/rejected item returns conflict.
4. Endpoint responses include timeline-ready data (messages, tool calls, items).

Acceptance:

1. API supports full lifecycle: create thread -> send message -> inspect run -> approve/reject item.
2. Errors are explicit and stable (400/404/409/422/500 as appropriate).

## 5) Tests

Files:

- `backend/tests/test_agent.py` (new)
- `backend/tests/conftest.py` (fixtures for agent env/files)

Test cases:

1. Thread and message history retrieval.
2. Run persistence with final assistant message requirement.
3. Tool call logging.
4. Proposal creation for each change type.
5. Approve flow creates resource and transitions state.
6. Reject flow transitions state without resource creation.
7. Repeated approve is idempotent/conflict-safe.
8. Entry apply from agent proposal always sets `status=PENDING_REVIEW`.

Acceptance:

1. `uv run pytest` passes including new test module.

## Frontend Implementation TODO

## 1) Agent Panel Shell

Files:

- `frontend/src/App.tsx`
- new components under `frontend/src/components/agent/*`
- new page/container under `frontend/src/pages/AgentPanel.tsx` (or equivalent)

Tasks:

1. Add right sidebar/panel toggle in app shell.
2. Keep existing routes/pages unchanged.
3. Preserve responsive behavior for desktop + mobile.

Acceptance:

1. Agent panel is accessible globally.
2. Existing pages still function without regressions.

## 2) Agent API Client + Types

Files:

- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`

Tasks:

1. Add typed APIs for new agent endpoints.
2. Add domain types for:
   - thread
   - message
   - run
   - tool call
   - change item
   - review action

Acceptance:

1. Query/mutation hooks can render full history and review queue without `any` casts.

## 3) Timeline + History Navigation

Tasks:

1. Thread list UI with create/select behavior.
2. Timeline UI for selected thread:
   - user/assistant messages
   - tool call blocks
   - change item cards
3. Show assistant final message distinctly from tool logs.

Acceptance:

1. Users can navigate old threads and inspect complete interaction history.

## 4) Review UI (Per Item)

Tasks:

1. For each `PENDING_REVIEW` item:
   - show payload preview
   - show rationale
   - Approve/Reject actions
2. For entry proposals:
   - allow edit-before-approve in V1
3. For tag/entity proposals:
   - no edit-before-approve in V1 (approve/reject only)
4. Reflect statuses in UI (`PENDING_REVIEW`, `APPLIED`, `REJECTED`, etc.).

Acceptance:

1. Approve/reject updates state immediately and stays consistent after refresh.
2. Created resources are visible in existing app pages after cache invalidation.

## ReAct Graph Behavior Contract

1. Every run must end with one assistant final message.
2. Final message should include:
   - direct answer (if Q&A intent)
   - summary of proposed items (if append intent)
   - clear next action prompt ("review pending items")
3. Tool call traces are not hidden:
   - stored in DB
   - rendered in timeline

## Operational/Dev TODO

1. Update dependencies in `pyproject.toml` (LangChain, LangGraph, OpenRouter-compatible client path).
2. Ensure installs use `uv sync --extra dev`.
3. Update startup docs with new required envs.
4. Validate migration + tests in local workflow.

## Documentation TODO (Required in same work item)

When implementation starts, update at minimum:

1. `README.md`
   - new env vars
   - agent feature status and run path
2. `docs/backend.md`
   - agent runtime/services/routers
3. `docs/api.md`
   - full `agent` endpoint contract
4. `docs/data-model.md`
   - new agent tables and state fields
5. `docs/frontend.md`
   - agent panel architecture and interaction flow
6. `docs/architecture.md`
   - AI-native flow and review boundary
7. `docs/development.md`
   - local setup + testing commands for agent feature

## Milestones

## Milestone 1 - Backend Foundation

1. Migration + models + schemas.
2. Thread/message/run storage.
3. Basic ReAct loop with read tools only.
4. Final-message enforcement.

Exit criteria:

1. Send message and receive final assistant response with persisted history.

## Milestone 2 - Proposal + Review Engine

1. Add proposal tools for entry/tag/entity create.
2. Persist `PENDING_REVIEW` items.
3. Add approve/reject endpoints and transactional apply service.

Exit criteria:

1. Approving an item creates exactly one domain resource.
2. Entry created via agent is `PENDING_REVIEW`.

## Milestone 3 - Frontend Panel + History + Review

1. Global agent panel.
2. Thread navigation and timeline.
3. Tool call rendering.
4. Per-item review UI with edit-before-approve for entries.

Exit criteria:

1. End-to-end manual flow works entirely through UI.

## Milestone 4 - Hardening

1. Full backend tests for lifecycle and idempotency.
2. UX polish for error/loading states.
3. Complete docs synchronization.

Exit criteria:

1. `uv run pytest` and frontend build pass.
2. Docs reflect implemented behavior exactly.

## Risks and Constraints

1. Model output reliability:
   - Mitigate with strict tool input schemas and server-side validation.
2. Duplicate/near-duplicate creations:
   - V1 relies on human review; no auto-dedupe apply.
3. Cost/latency:
   - Bound with max tool steps, context window trimming, and thread pagination.
4. Security/privacy:
   - keep agent images local in app storage
   - do not expose raw DB credentials or unrestricted execution tools.

## Suggested Implementation Order (Concrete)

1. DB migration + ORM + Pydantic.
2. Agent runtime service + read tools + final message contract.
3. Proposal tools + review/apply service.
4. Agent router endpoints.
5. Frontend API/types.
6. Frontend panel/timeline/review UI.
7. Tests.
8. Docs updates.
