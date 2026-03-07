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
  - LiteLLM adapter, retry policy, stream handling, usage normalization, and observability metadata
- `backend/services/agent/pricing.py`
  - LiteLLM-backed pricing helper
- `backend/services/agent/tool_args.py`
  - tool argument schemas and nested JSON normalization
- `backend/services/agent/tool_handlers_read.py`
  - read tools and `send_intermediate_update`
- `backend/services/agent/tool_handlers_propose.py`
  - proposal CRUD tools and pending-proposal edit or remove tools
- `backend/services/agent/proposal_patching.py`
  - patch-map helpers for pending proposal edits
- `backend/services/agent/tool_runtime.py`
  - tool registry, schema composition, and execution policy
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
- `Current User Context` is rendered as `Account Context`, `User Memory`, and `Entity Category Reference`
- duplicate-entry checks should happen before new entry proposals
- tag/entity naming should stay canonical and generalized
- tag-delete proposals may proceed while referenced; proposal previews should surface impact counts and apply removes entry junction rows by cascade
- `send_intermediate_update` is required as the first tool call when tool work is needed
- model-facing tool interfaces avoid domain IDs and use names or selectors instead

## Agent Router

- `backend/routers/agent.py`
- delegates message validation and run lifecycle policy to `backend/services/agent/execution.py`
- delegates attachment storage and cleanup to `backend/services/agent/attachments.py`
- starts background runs with injected session factories from `get_session_maker()`
- all agent endpoints require admin principal

Endpoints:

- `GET /api/v1/agent/threads`
- `POST /api/v1/agent/threads`
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
- run snapshots aggregate usage metrics and derived USD pricing

## Current Agent Execution Behavior

- runs support both background execution and SSE execution
- streamed runs emit transient `reasoning_delta`, `text_delta`, and ordered persisted `run_event` rows
- streamed tool lifecycle `run_event` payloads include a compact top-level `tool_call` snapshot so clients can render the tool name immediately without fetching full payloads
- `send_intermediate_update` is persisted as a `reasoning_update` event, not as a fake tool call
- attachment-bearing user turns reach the model as ordered content parts: attachment text, then attachment images, then the typed user prompt
- PDFs use PyMuPDF first and then local Tesseract OCR only when native text extraction fails
- interruption marks runs as `failed` and injects interruption context into the next turn
- pending proposals can be updated or removed in later turns while still `PENDING_REVIEW`

## Related Docs

- `docs/api/agent.md`
- `docs/agent-billing-assistant.md`
- `docs/architecture.md`
