# Architecture

## Goal

Bill Helper is a local-first personal finance ledger with AI-assisted, review-gated append-only change proposals.

## Runtime Topology

- Frontend SPA: React + TypeScript + Vite (`http://localhost:5173`)
- Backend API: FastAPI (`http://localhost:8000`)
- Database: SQLite (`{data_dir}/bill_helper.db`, default `~/.local/share/bill_helper/`)
- Canonical user file storage: local filesystem under `{data_dir}/user_files/{user_id}/uploads`
- Per-user agent workspace resources: one named Docker volume plus one stopped-by-default named container definition per user

## High-Level Components

- `frontend`: UI pages, agent panel, API calls, cache orchestration
- `backend/routers`: HTTP endpoint layer
- `backend/services`: domain logic, canonical file storage, agent runtime/review logic, and per-user workspace provisioning
- `backend/models_finance.py` + `backend/models_agent.py` + `backend/models_files.py`: SQLAlchemy ORM tables
- `alembic`: schema migrations

## Core Decisions

- migration-first DB lifecycle via Alembic
- integer minor-unit money representation
- first-class typed entry groups with derived graph edges from direct membership
- `Entity` is the root identity model; `Account` is a shared-primary-key subtype table (`accounts.id == entities.id`)
- account semantics are determined by subtype membership in `accounts`, not by `entities.category`
- soft-delete entries with direct group-membership cleanup
- AI boundary is append-only proposal creation plus explicit human review apply/reject
- direct API deletes and agent-applied deletes use the same canonical semantics for tag/entity/account removal
- durable user-visible files are canonicalized into a per-user registry before higher-level agent attachment linkage
- user creation/bootstrap eagerly provisions deterministic host and Docker workspace resources for later execution tooling

## Backend Layering

- routers: request validation + status mapping
- services: normalization, calculations, group validation/graph derivation, agent orchestration
- models: persistence structure and relationships in `models_finance.py` and `models_agent.py`
- schemas: API contracts in `schemas_finance.py` and `schemas_agent.py`
- app bootstrap: explicit `create_app()` factory (uvicorn factory mode), avoiding import-time initialization side effects

## Agent Architecture

## Run Lifecycle

1. user sends message to `/api/v1/agent/threads/{thread_id}/messages` (background) or `/api/v1/agent/threads/{thread_id}/messages/stream` (SSE)
2. backend persists user message and attachments
3. backend creates `agent_runs` row (`running`)
4. runtime executes bounded tool-calling loop via LiteLLM using configured provider model
5. each tool call is persisted to `agent_tool_calls`
6. `bh` proposal commands create `agent_change_items` (`PENDING_REVIEW`)
7. stream path emits incremental `text_delta` plus persisted `run_event` payloads (run start/finish, reasoning updates, and per-tool lifecycle events)
8. runtime enforces a final assistant message and marks run `completed` or `failed`

## Review Boundary

- agent runtime cannot directly write `entries`, `tags`, `entities`
- only review endpoints apply domain mutations
- review is strictly per item (`approve` / `reject`)
- apply writes audit action rows (`agent_review_actions`)
- approved entry proposals create `entries` rows directly (no entry-level status column)

## Tooling Model (Current)

Model-visible tools:

- `terminal`
- `send_intermediate_update`
- `rename_thread`
- `add_user_memory`

Execution model:

- `terminal` executes inside the per-user workspace container
- the workspace receives injected backend/auth/thread/run env per invocation
- Bill Helper app-state reads and proposal/review actions go through the installed `bh` CLI
- local file and shell work stays in the workspace terminal rather than adding more specialized model-facing tools

Contract notes:

- the model-visible tool catalog is intentionally small; app operations should prefer `bh` over raw `curl` or ad hoc Python when a command exists
- proposal lifecycle remains review-gated even though the agent now reaches it through CLI commands instead of direct proposal tools
- thread-scoped proposal commands require the active thread and run context so proposal history stays attached to the invoking run

## Agent Internal Boundaries (Refactor Baseline)

- `runtime.py`: public runtime facade and stable model-call monkeypatch seam (`call_model`, `call_model_stream`, `calculate_context_tokens`)
- `runtime_support/`: grouped run-lifecycle and tool-turn internals behind the runtime facade
- `runtime_state.py`: runtime event/tool-call/terminal-state persistence helpers
- `run_orchestrator.py`: shared step-state machine used by runtime sync/stream flows and benchmark adapters
- `message_history.py`: public thread-to-model message assembly facade
- `message_history_content.py`: attachment-backed user-content shaping and entity-category prompt context
- `message_history_prefixes.py`: review-window queries and interruption-prefix composition
- `attachment_content.py`: public attachment-content seam plus vision capability checks used by attachment helpers and `read_image`
- `docling_convert.py` / `agent_attachment_bundle.py`: Docling-based agent attachment parsing and bundle layout
- `attachment_content_assembly.py`: attachment part assembly and workspace image-path hint helpers
- `user_context.py`: current-user/account context normalization and truncation for prompt assembly
- `model_client.py`: thin public seam for the LiteLLM client contract
- `model_client_support/`: grouped environment, streaming, usage-normalization, and retrying client internals behind the public model-client seam
- `tool_runtime.py`: thin public seam for tool contracts and execution entrypoints
- `tool_runtime_support/`: grouped tool metadata, schema-building, family registries, and retry/error policy behind the public tool-runtime seam
- `apply/`: change-type apply package for review-time resource application
- `reviews/`: approval/rejection transitions, dependency checks, override normalization, and audit writes
- `benchmark_interface.py`: benchmark-facing case execution contract returning normalized predictions/trace payloads

## Frontend State Strategy

Remote state:

- TanStack Query for all API domains

Agent state:

- thread list query
- selected-thread detail query
- message send + approve/reject mutations
- optimistic user/assistant message placeholders while runs are in-flight
- panel-level UI split:
  - render shell: `frontend/src/features/agent/AgentPanel.tsx`
  - controller/presentation modules: `frontend/src/features/agent/panel/*`
  - run rendering/derivation: `frontend/src/features/agent/AgentRunBlock.tsx`, `frontend/src/features/agent/activity.ts`
  - feature-owned location keeps agent UI beside its tests/review/timeline helpers instead of under generic shared components

Cross-page consistency:

- approving change items invalidates ledger queries (`entries`, `tags`, `entities`, `users`, `dashboard`, `currencies`)
- deleting an account/entity preserves denormalized entry labels and surfaces missing-entity markers instead of erasing history text

## Data Flow Summary

### Standard ledger writes

1. page form submits JSON
2. router validates
3. service mutates models
4. commit + response
5. frontend cache invalidation

### Agent-assisted writes

1. user prompts agent
2. runtime gathers context via workspace terminal commands and records traces
3. runtime creates proposal item(s) only
4. reviewer approves/rejects each item
5. apply service creates resource transactionally
6. UI refreshes across existing pages

## Security / Scope (Current)

- password-backed bearer sessions gate the web app and API
- owner-scoped finance and agent reads reuse the same principal visibility rules
- agent threads are user-owned instead of admin-global; admins can still access everything or impersonate a user
- review apply uses the approving reviewer principal for scoped entry resolution and owner attribution, not mutable runtime settings identity
- only image and PDF attachments are accepted in agent messages
- active agent runs have workspace terminal execution through `terminal`; Bill Helper app operations are expected to flow through `bh`
- provisioned workspaces mount only the owning user's canonical upload root at `/workspace/uploads` as read-only and do not expose `bill_helper.db`

## Out of Scope (Current)

- bank sync / CSV ingestion
- autonomous background agent runs
- non-LiteLLM model client implementations

## Deferred / Roadmap

- Live bank sync and generalized multi-bank CSV ingestion workflows
- Finer-grained RBAC beyond the current admin/non-admin split
- Native-client and mobile login UX beyond bearer-token configuration
- FX conversion to a configurable base currency
- Autonomous background agent runs (scheduled or event-driven)
