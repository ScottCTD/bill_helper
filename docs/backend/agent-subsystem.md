# Backend Agent Subsystem

## Agent Service Layout

- `backend/services/agent/runtime.py`
  - run lifecycle coordinator and stable execution seam (`call_model`, `call_model_stream`, `calculate_context_tokens`)
- `backend/services/agent/run_orchestrator.py`
  - shared run-step state machine for sync, stream, and benchmark adapters
- `backend/services/agent/protocol_helpers.py`
  - canonical tool-call decoding and usage-shape normalization helpers
- `backend/services/agent/error_policy.py`
  - shared recoverable fallback and contextual logging helpers
- `backend/services/agent/context_tokens.py`
  - best-effort prompt-size estimation through LiteLLM `token_counter`
- `backend/services/agent/prompts.py`
  - system prompt composition and tool-discipline policy
- `backend/services/agent/message_history.py`
  - persisted thread history to model-ready messages, including attachment ordering and interruption context
- `backend/services/agent/model_client.py`
  - LiteLLM adapter, retry policy, stream handling, and usage normalization
- `backend/services/agent/pricing.py`
  - LiteLLM-backed pricing helper
- `backend/services/agent/tool_args.py`
  - tool argument schemas and nested JSON normalization
- `backend/services/agent/tool_handlers_read.py`
  - read tools and `send_intermediate_update`
- `backend/services/agent/tool_handlers_threads.py`
  - `rename_thread` handler for short thread-topic updates
- `backend/services/agent/tool_handlers_propose.py`
  - proposal CRUD tools and pending-proposal edit or remove tools
- `backend/services/agent/entry_references.py`
  - shared entry lookup helpers for `entry_id` aliases, selector fallback, and public entry snapshots
- `backend/services/agent/group_references.py`
  - shared group-id alias lookup plus public group summary/detail formatting for `list_groups` and group proposals
- `backend/services/agent/proposal_metadata.py`
  - canonical mapping from `change_type` to proposal domain/action/tool name for `list_proposals`, history, and review summaries
- `backend/services/agent/proposal_patching.py`
  - patch-map helpers for pending proposal edits
- `backend/services/agent/tool_runtime.py`
  - tool registry, schema composition, and execution policy
- `backend/services/agent/threads.py`
  - thread-title normalization plus rename persistence helpers shared by the router and tool handler
- `backend/services/agent/tools.py`
  - thin composition facade for runtime interfaces
- `backend/services/agent/change_contracts.py`
  - shared proposal/apply payload normalization
- `backend/services/agent/execution.py`
  - message intake, run start, background continuation, and execution facade for non-runtime callers
- `backend/services/agent/attachments.py`
  - attachment file lifecycle helpers
- `backend/services/agent/attachment_content.py`
  - attachment parsing, PDF text or OCR, and model-content materialization
- `backend/services/agent/user_context.py`
  - current-user and account-context normalization
- `backend/services/agent/runtime_state.py`
  - run-event, tool-call, and terminal-state persistence helpers
- `backend/services/agent/benchmark_interface.py`
  - benchmark-facing `run_benchmark_case` contract
- `backend/services/agent/review.py`
  - approve or reject workflow and state transitions
- `backend/services/agent/change_apply.py`
  - concrete apply handlers for approved proposals
- `backend/services/agent/serializers.py`
  - timeline-ready serializer helpers

## Prompt And Tooling Rules

- prompt policy is organized into explicit sections for tool discipline, proposal workflows, execution, and final response behavior
- `Current User Context` includes timezone/date bullets plus `Entity Category Reference` and `Account Context`
- `Agent Memory` is rendered as a markdown unordered list built from persisted runtime-setting memory items
- duplicate-entry checks should happen before new entry proposals
- tag/entity naming should stay canonical and generalized
- tag-delete proposals may proceed while referenced; proposal previews should surface impact counts and apply removes entry junction rows by cascade
- `send_intermediate_update` is required as the first tool call when tool work is needed
- `add_user_memory` is an add-only tool for explicit remember-this requests; mutate/remove requests must be declined
- `rename_thread` should run right after the first user message in a new thread, then only when the user explicitly asks or the topic materially changes
- model-facing tool interfaces avoid requiring full domain IDs; entry mutations prefer `entry_id` aliases from `list_entries` with selector fallback
- existing-group mutations prefer `group_id` aliases from `list_groups`
- the prompt has a dedicated `Grouping` section that combines fixed `BUNDLE` / `SPLIT` / `RECURRING` semantics, examples, and workflow guidance
- after proposing a new entry, the prompt instructs the agent to check whether an existing recurring, split, or bundle group should absorb it and to propose the membership change when needed
- group membership proposals may reference pending `create_group` and `create_entry` proposal ids in the same thread; approval is blocked until those dependencies are applied

## Agent Router

- `backend/routers/agent.py`
- delegates message validation and run lifecycle policy to `backend/services/agent/execution.py`
- delegates attachment storage and cleanup to `backend/services/agent/attachments.py`
- starts background runs with injected session factories from `get_session_maker()`
- all agent endpoints require admin principal

Endpoints:

- `GET /api/v1/agent/threads`
- `POST /api/v1/agent/threads`
- `PATCH /api/v1/agent/threads/{thread_id}`
- `DELETE /api/v1/agent/threads/{thread_id}`
- `GET /api/v1/agent/threads/{thread_id}`
- `POST /api/v1/agent/threads/{thread_id}/messages`
- `POST /api/v1/agent/threads/{thread_id}/messages/stream`
- `GET /api/v1/agent/runs/{run_id}`
- `GET /api/v1/agent/tool-calls/{tool_call_id}`
- `POST /api/v1/agent/runs/{run_id}/interrupt`
- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`
- `GET /api/v1/agent/attachments/{attachment_id}`

## Thread Detail Behavior

- `GET /api/v1/agent/threads/{thread_id}` returns `current_context_tokens`
- thread detail returns compact tool-call snapshots by default (`has_full_payload=false`)
- full tool payloads are fetched through `GET /api/v1/agent/tool-calls/{tool_call_id}`
- runs persist ordered `events[]` rows for replayable timeline activity
- runs also carry their `change_items`; the frontend flattens those per-run proposal lists into one thread review model
- run snapshots aggregate usage metrics and derived USD pricing; prompt-side costs use cache-aware LiteLLM rates when cache usage is present and stay folded into the existing `input_cost_usd`/`total_cost_usd` fields

## Current Agent Execution Behavior

- runs support both background execution and SSE execution
- streamed runs emit transient `reasoning_delta`, `text_delta`, and ordered persisted `run_event` rows
- streamed tool lifecycle `run_event` payloads include a compact top-level `tool_call` snapshot so clients can render the tool name immediately without fetching full payloads
- clients may hydrate a streamed `rename_thread` tool call immediately and update the visible thread title before the final assistant message arrives
- `send_intermediate_update` is persisted as a `reasoning_update` event, not as a fake tool call
- attachment-bearing user turns reach the model as ordered content parts: attachment text, then attachment images, then the typed user prompt
- PDFs use PyMuPDF first and then local Tesseract OCR only when native text extraction fails
- interruption marks runs as `failed` and injects interruption context into the next turn
- pending proposals can be updated or removed in later turns while still `PENDING_REVIEW`
- reviewed proposal context now includes reviewer override values when `payload_override` changed the approved payload, so later turns can see concrete edited values instead of only changed field names

## Review And Apply Behavior

- `backend/services/agent/review.py` accepts reviewer `payload_override` for create/update entry, tag, entity, and group proposals while keeping the approve endpoint contract unchanged
- group-member approvals that reference pending `create_group` / `create_entry` proposals are blocked until those dependencies are applied; rejected or failed dependencies leave the member proposal unapprovable until edited or removed
- `backend/services/agent/change_apply.py` still owns the actual domain mutation after approval, including group create/rename/delete and group membership add/remove
- `backend/services/agent/message_history.py` prepends compact review outcome lines before the next user feedback message and includes `review_override=...` when reviewer edits changed the applied payload
- group-member proposal previews now carry enough entry fields, including `markdown_notes`, for the frontend to render a locked full-entry snapshot during review

## Related Docs

- `docs/api/agent.md`
- `docs/agent-billing-assistant.md`
- `docs/architecture.md`
