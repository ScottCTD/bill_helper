# Backend Agent Subsystem

## Agent Service Layout

- `backend/services/agent/runtime.py`
  - public runtime facade: run lifecycle entrypoints plus stable execution seams (`call_model`, `call_model_stream`, `calculate_context_tokens`)
- `backend/services/agent/runtime_support/`
  - grouped runtime internals: `lifecycle.py` for run creation, replay, interrupt, and terminal persistence; `tool_turns.py` for assistant-content cleanup and queued tool-turn preparation
- `backend/services/agent/runtime_loop.py`
  - runtime adapter package-less split for tool-turn preparation, non-stream and stream run-loop adapters, and terminal completion/error handling
- `backend/services/agent/run_orchestrator.py`
  - shared run-step state machine for sync, stream, and benchmark adapters
- `backend/services/agent/protocol_helpers.py`
  - canonical tool-call decoding and usage-shape normalization helpers
- `backend/services/agent/error_policy.py`
  - shared recoverable fallback and contextual logging helpers
- `backend/services/agent/context_tokens.py`
  - best-effort prompt-size estimation through LiteLLM `token_counter`
- `backend/services/agent/prompts.py`
  - system prompt composition, tool-discipline policy, and response-surface guidance
- `backend/services/agent/message_history.py`
  - public message-history facade for thread-to-model message assembly
- `backend/services/agent/message_history_content.py`
  - attachment-backed user-content shaping plus entity-category prompt context
- `backend/services/agent/message_history_prefixes.py`
  - review-result and interruption-prefix query helpers for the current turn
- `backend/services/agent/model_client.py`
  - thin public seam re-exporting the LiteLLM client contract
- `backend/services/agent/model_client_support/`
  - grouped model-client internals: `client.py` for the retrying LiteLLM adapter, `environment.py` for provider/env validation and prompt-cache support, `streaming.py` for streamed delta reconciliation, and `usage.py` for usage-shape normalization
- `backend/services/agent/tool_runtime.py`
  - thin public seam for tool contracts plus runtime execution entrypoints
- `backend/services/agent/tool_runtime_support/`
  - grouped tool-runtime internals: `definitions.py` for tool metadata, `schema.py` for OpenAI schema inlining, `catalog_*.py` for internal tool-family registration plus the reduced model-visible runtime set, `catalog.py` for the merged registry, and `execution.py` for retry/error policy
- `backend/services/agent/pricing.py`
  - LiteLLM-backed pricing helper
- `backend/services/agent/tool_args/`
  - focused tool-input package: `read.py` for read filters, `shared.py` for progress/common args, `threads.py` for thread rename args, `memory.py` for add-only memory args, and `proposal_admin.py` for pending-proposal/group-membership tool inputs
- `backend/services/agent/read_tools/`
  - read-tool package: `entries.py` for entry lookup ranking, `catalog.py` for tag/entity/account lookup, `groups.py` for group lookup/detail formatting, `proposals.py` for proposal history inspection, and `common.py` for shared ranking/principal-scope formatting helpers
- `backend/services/agent/session_tools/`
  - session-tool package: `progress.py` for `send_intermediate_update`, `memory.py` for add-only persistent memory appends, and `threads.py` for short thread-topic updates
- `backend/services/agent/workspace_command.py`
  - workspace terminal execution helper that injects per-command auth/thread/run context and executes shell commands inside the per-user workspace container
- `backend/services/agent/proposals/`
  - proposal-family package: `common.py` for shared proposal/thread helpers, `catalog.py` for tag/entity/account proposals, `entries.py` for entry proposal handlers, `groups.py` for group CRUD proposal flows, `group_memberships/` for membership canonicalization, validation, and handlers, family-owned normalization modules plus a small `normalization.py` registry for proposal payload canonicalization, and `pending.py` for pending-proposal edit/remove tools
- `backend/services/agent/entry_references.py`
  - shared entry lookup helpers for `entry_id` aliases, selector fallback, and public entry snapshots
- `backend/services/agent/group_references.py`
  - shared group-id alias lookup plus compact public group summary/detail formatting for `list_groups` and group proposals
- `backend/services/agent/proposal_metadata.py`
  - canonical mapping from `change_type` to proposal domain/action/tool name for proposal history formatting, CLI responses, and review summaries
- `backend/services/agent/proposal_patching.py`
  - patch-map helpers for pending proposal edits
- `backend/services/agent/threads.py`
  - thread-title normalization plus rename persistence helpers shared by the router and tool handler
- `backend/services/agent/tools.py`
  - thin composition facade for runtime interfaces
- `backend/services/agent/change_contracts/`
  - proposal/apply payload contracts split by catalog, entry, and group domains, with shared normalization and patch helpers
- `backend/services/agent/execution.py`
  - message intake, run start, background continuation, and execution facade for non-runtime callers
- `backend/services/agent/attachments.py`
  - message-to-canonical-file linkage helpers
- `backend/services/user_files.py`
  - canonical per-user file storage, hashing, path management, and artifact promotion helpers
- `backend/services/agent_workspace.py`
  - per-user workspace spec building plus Docker-backed workspace provisioning/start-stop helpers
- `backend/services/docker_cli.py`
  - thin Docker CLI adapter for image, volume, container, and exec lifecycle commands
- `backend/services/agent/attachment_content.py`
  - public attachment-content seam for message-history callers and tests
- `backend/services/agent/attachment_content_pdf.py`
  - PDF text extraction, OCR fallback, page rendering, and recoverable parse logging
- `backend/services/agent/attachment_content_assembly.py`
  - attachment display-name, data-url, and model-content part assembly helpers
- `backend/services/agent/user_context.py`
  - current-user and account-context normalization
- `backend/services/agent/runtime_state.py`
  - run-event, tool-call, and terminal-state persistence helpers
- `backend/services/agent/benchmark_interface.py`
  - benchmark-facing `run_benchmark_case` contract
- `backend/services/agent/reviews/`
  - review-workflow package: `common.py` for change-item record helpers, `dependencies.py` for approval blockers, `overrides.py` for payload-override normalization, and `workflow.py` for approve/reject/reopen state transitions
- `backend/services/agent/apply/`
  - apply-family package: `common.py` for lookup and applied-reference helpers, `catalog.py` for tag/entity/account mutations, `entries.py` for entry mutations, `groups.py` for group and membership mutations, and `dispatch.py` for change-type routing
- `backend/services/agent/serializers.py`
  - timeline-ready serializer helpers, including compatibility filtering for legacy unsupported change-item rows and surface-aware terminal reply shaping

## Prompt And Tooling Rules

- prompt policy is organized into explicit sections for tool discipline, proposal workflows, execution, and final response behavior
- prompt rendering carries a run surface hint so Telegram-directed turns can request plain-text-friendly final answers
- `Current User Context` includes timezone/date bullets plus `Entity Category Reference` and `Account Context`
- `Agent Memory` is rendered as a markdown unordered list built from persisted runtime-setting memory items
- the model-visible tool catalog is intentionally small: `rename_thread`, `send_intermediate_update`, `add_user_memory`, and `run_workspace_command`
- app-state reads and proposal lifecycle work now flow through the workspace terminal and the installed `billengine` CLI rather than the older large direct read/proposal tool list
- duplicate-entry checks should happen before new entry proposals
- tag/entity naming should stay canonical and generalized
- tag-delete proposals may proceed while referenced; proposal previews should surface impact counts and apply removes entry junction rows by cascade
- `send_intermediate_update` is required as the first tool call when tool work is needed
- `add_user_memory` is an add-only tool for explicit remember-this requests; mutate/remove requests must be declined
- `rename_thread` should run right after the first user message in a new thread, then only when the user explicitly asks or the topic materially changes
- untitled threads are runtime-gated to expose only the `rename_thread` tool on the first model step; most models also receive an explicit required `tool_choice`, but `openrouter/qwen/qwen3.5-27b` falls back to tool-list restriction only because OpenRouter rejects explicit `tool_choice` for that model in thinking mode
- `run_workspace_command` injects backend URL, a short-lived bearer session, current thread id, and current run id on every execution; the agent does not supply those manually
- the prompt has a dedicated `Grouping` section that combines fixed `BUNDLE` / `SPLIT` / `RECURRING` semantics, examples, and workflow guidance
- after proposing a new entry, the prompt instructs the agent to check whether an existing recurring, split, or bundle group should absorb it and to propose the membership change when needed
- group membership proposals may reference pending `create_group` and `create_entry` proposal ids in the same thread; approval is blocked until those dependencies are applied
- stored group-member proposal payloads canonicalize existing `group_id` / `entry_id` aliases and pending create-proposal ids to their full ids so pending-conflict detection, dependency blocking, and apply all operate on the same references

## Agent Router

- `backend/routers/agent.py`
  - thin aggregator that includes the split HTTP modules below
- `backend/routers/agent_threads.py`
  - thread list/detail plus message-send and stream endpoints
- `backend/routers/agent_runs.py`
  - run detail, tool-call detail, and interrupt endpoints
- `backend/routers/agent_proposals.py`
  - thread-scoped proposal list/get/create/update/delete HTTP translation for the `billengine` CLI
- `backend/routers/agent_reviews.py`
  - approve/reject/reopen HTTP translation for review actions
- `backend/routers/agent_attachments.py`
  - attachment file download endpoint
- `backend/routers/agent_threads.py`
  - also owns the message-create HTTP translation, SSE event formatting, and background-session launch helpers used only by the thread send endpoints
- delegates message validation and run lifecycle policy to `backend/services/agent/execution.py`
- accepts an optional `surface` form field on message-send routes and persists it onto the created run for background continuation
- delegates canonical upload storage to `backend/services/user_files.py` through `backend/services/agent/execution.py`
- starts background runs with injected session factories from `get_session_maker()`
- all agent endpoints require an explicit authenticated request principal; non-admin users are scoped to their own threads while admins can access every thread

Endpoints:

- `GET /api/v1/agent/threads`
- `POST /api/v1/agent/threads`
- `PATCH /api/v1/agent/threads/{thread_id}`
- `DELETE /api/v1/agent/threads/{thread_id}`
- `GET /api/v1/agent/threads/{thread_id}`
- `POST /api/v1/agent/threads/{thread_id}/messages`
- `POST /api/v1/agent/threads/{thread_id}/messages/stream`
- `GET /api/v1/agent/threads/{thread_id}/proposals`
- `GET /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`
- `POST /api/v1/agent/threads/{thread_id}/proposals`
- `PATCH /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`
- `DELETE /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`
- `GET /api/v1/agent/runs/{run_id}`
- `GET /api/v1/agent/tool-calls/{tool_call_id}`
- `POST /api/v1/agent/runs/{run_id}/interrupt`
- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`
- `POST /api/v1/agent/change-items/{item_id}/reopen`
- `GET /api/v1/agent/attachments/{attachment_id}`

## Thread Detail Behavior

- `GET /api/v1/agent/threads/{thread_id}` returns `current_context_tokens`
- message-send endpoints accept optional multipart `model_name`; when present it must match one of the resolved runtime `available_agent_models`
- thread detail returns compact tool-call snapshots by default (`has_full_payload=false`)
- thread detail keeps `configured_model_name` as the resolved runtime default while each run persists its own `model_name`; `current_context_tokens` follows the newest run model when a thread already has runs
- full tool payloads are fetched through `GET /api/v1/agent/tool-calls/{tool_call_id}`
- runs persist ordered `events[]` rows for replayable timeline activity
- runs also carry their `change_items`; the frontend flattens those per-run proposal lists into one thread review model
- serializer output skips legacy persisted change rows whose enum values are still recognized for hydration but no longer part of the supported client review surface
- run snapshots aggregate usage metrics and derived USD pricing; prompt-side costs use cache-aware LiteLLM rates when cache usage is present and stay folded into the existing `input_cost_usd`/`total_cost_usd` fields

## Current Agent Execution Behavior

- runs support both background execution and SSE execution
- each run persists a `surface` hint so later execution and polling can distinguish Telegram-originated runs from default app runs
- streamed runs emit transient `reasoning_delta`, `text_delta`, and ordered persisted `run_event` rows
- streamed tool lifecycle `run_event` payloads include a compact top-level `tool_call` snapshot so clients can render the tool name immediately without fetching full payloads
- clients may hydrate a streamed `rename_thread` tool call immediately and update the visible thread title before the final assistant message arrives
- `send_intermediate_update` is persisted as a `reasoning_update` event, not as a fake tool call
- malformed tool-call JSON now persists an explicit tool-call error with raw argument text and decode metadata instead of being silently rewritten to an empty argument object
- attachment-bearing user turns reach the model as ordered content parts: attachment text, then attachment images, then the typed user prompt
- new agent uploads are written into the canonical per-user store under `{data_dir}/user_files/{owner_user_id}/uploads/...`, and `agent_message_attachments` link to those canonical rows instead of owning file metadata directly
- PDFs use PyMuPDF first and then local Tesseract OCR only when native text extraction fails
- interruption marks runs as `failed` and injects interruption context into the next turn
- pending proposals can be updated or removed in later turns while still `PENDING_REVIEW`
- reviewed proposal context now includes reviewer override values when `payload_override` changed the approved payload, so later turns can see concrete edited values instead of only changed field names
- run snapshots expose persisted `surface`, explicit `reply_surface`, and `terminal_assistant_reply`, so read-time formatting overrides do not masquerade as the stored run surface
- deleting a thread removes attachment linkage rows but intentionally leaves canonical uploaded payload files in place
- the active agent runtime now exposes full workspace terminal execution through `run_workspace_command`; app-state operations are expected to go through the installed `billengine` CLI inside that terminal
- proposal HTTP routes are thread-scoped and require `X-Bill-Helper-Agent-Run-Id` so `billengine` can keep new or updated proposals attached to the invoking run

## Review And Apply Behavior

- `backend/services/agent/reviews/` accepts reviewer `payload_override` for create/update entry, tag, entity, and group proposals across approve, reject, and reopen actions while leaving `APPLIED` items immutable
- invalid reviewer overrides fail during payload normalization and leave the proposal unchanged instead of marking it `APPLY_FAILED`
- review workflow failures now surface through typed `PolicyViolation` statuses instead of router-local `ValueError` string matching, so approve/reject/reopen keep one error contract for `400`, `409`, and `422` responses
- group-member approvals that reference pending `create_group` / `create_entry` proposals are blocked until those dependencies are applied; rejected or failed dependencies leave the member proposal unapprovable until edited or removed
- apply-time group-member resolution canonicalizes existing short `group_id` and `entry_id` aliases to full ids before scoped lookup and membership matching, so approval semantics match proposal-time alias handling
- review apply uses the approving reviewer principal for principal-scoped entry lookup and for owner attribution on newly created entry/account/group resources; mutable runtime settings remain only as a non-request fallback
- pending-proposal update flows re-run group conflict checks after normalization, so revised group create/update/delete/member proposals cannot be patched into duplicate or conflicting pending states
- `backend/services/agent/apply/` owns the actual domain mutation after approval, including group create/rename/delete and group membership add/remove
- `backend/services/agent/message_history_prefixes.py` prepends compact review outcome lines before the next user feedback message and includes `review_override=...` when reviewer edits changed the applied payload
- group-member proposal previews now carry enough entry fields, including `markdown_notes`, for the frontend to render a locked full-entry snapshot during review

## Related Docs

- `docs/api/agent.md`
- `docs/agent_billing_assistant.md`
- `docs/architecture.md`
