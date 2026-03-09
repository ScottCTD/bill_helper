# Architecture

## Goal

Bill Helper is a local-first personal finance ledger with AI-assisted, review-gated append-only change proposals.

## Runtime Topology

- Frontend SPA: React + TypeScript + Vite (`http://localhost:5173`)
- Backend API: FastAPI (`http://localhost:8000`)
- Database: SQLite (`{data_dir}/bill_helper.db`, default `~/.local/share/bill-helper/`)
- Agent upload storage: local filesystem under `{data_dir}/agent_uploads`

## High-Level Components

- `frontend`: UI pages, agent panel, API calls, cache orchestration
- `backend/routers`: HTTP endpoint layer
- `backend/services`: domain logic and agent runtime/review logic
- `backend/models`: SQLAlchemy ORM tables
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

## Backend Layering

- routers: request validation + status mapping
- services: normalization, calculations, group validation/graph derivation, agent orchestration
- models: persistence structure and relationships
- schemas: API contracts
- app bootstrap: explicit `create_app()` factory (uvicorn factory mode), avoiding import-time initialization side effects

## Agent Architecture

## Run Lifecycle

1. user sends message to `/api/v1/agent/threads/{thread_id}/messages` (background) or `/api/v1/agent/threads/{thread_id}/messages/stream` (SSE)
2. backend persists user message and attachments
3. backend creates `agent_runs` row (`running`)
4. runtime executes bounded tool-calling loop via LiteLLM using configured provider model
5. each tool call is persisted to `agent_tool_calls`
6. proposal tools create `agent_change_items` (`PENDING_REVIEW`)
7. stream path emits incremental `text_delta` plus persisted `run_event` payloads (run start/finish, reasoning updates, and per-tool lifecycle events)
8. runtime enforces a final assistant message and marks run `completed` or `failed`

## Review Boundary

- agent runtime cannot directly write `entries`, `tags`, `entities`
- only review endpoints apply domain mutations
- review is strictly per item (`approve` / `reject`)
- apply writes audit action rows (`agent_review_actions`)
- approved entry proposals create `entries` rows directly (no entry-level status column)

## Tooling Model (Current)

Read tools:

- `list_entries`
- `list_accounts`
- `list_tags`
- `list_entities`
- `list_proposals`

Proposal tools:

- entries: `propose_create_entry`, `propose_update_entry`, `propose_delete_entry`
- accounts: `propose_create_account`, `propose_update_account`, `propose_delete_account`
- tags: `propose_create_tag`, `propose_update_tag`, `propose_delete_tag`
- entities: `propose_create_entity`, `propose_update_entity`, `propose_delete_entity`

Contract notes:

- model-facing tool interfaces avoid requiring full domain IDs; entry mutations prefer `entry_id` aliases from `list_entries`
- account mutations are first-class proposals; generic entity proposals reject `category="account"` and account grounding/editing should use `list_accounts`
- entry update/delete fall back to selectors: `date + amount_minor + from_entity + to_entity + name`
- entry-id or selector ambiguity is reported to the model as a tool error so the model asks user clarification

## Agent Internal Boundaries (Refactor Baseline)

- `runtime.py`: run lifecycle coordinator and stable model-call monkeypatch seam (`call_model`, `call_model_stream`)
- `runtime_state.py`: runtime event/tool-call/terminal-state persistence helpers
- `run_orchestrator.py`: shared step-state machine used by runtime sync/stream flows and benchmark adapters
- `message_history.py`: message-history query flow and turn-level review/interruption prefix composition
- `attachment_content.py`: attachment parsing (PDF text/OCR, image payloads, vision capability checks)
- `user_context.py`: current-user/account context normalization and truncation for prompt assembly
- `model_client.py`: LiteLLM adapter and normalized model errors
- `model_client.py`: tenacity retries for model completion calls
- `change_apply.py`: change-type handler registry for review-time resource application
- `review.py`: approval/rejection transitions and audit writes
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
  - coordinator: `frontend/src/features/agent/AgentPanel.tsx`
  - presentation modules: `frontend/src/features/agent/panel/*`
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
2. runtime gathers context via read tools and records traces
3. runtime creates proposal item(s) only
4. reviewer approves/rejects each item
5. apply service creates resource transactionally
6. UI refreshes across existing pages

## Security / Scope (Current)

- single-user local mode; no auth RBAC yet
- agent actor label uses configured current-user name
- only image and PDF attachments are accepted in agent messages
- no arbitrary code execution tools in agent runtime

## Out of Scope (Current)

- bank sync / CSV ingestion
- autonomous background agent runs
- non-LiteLLM model client implementations

## Deferred / Roadmap

- Live bank sync and generalized multi-bank CSV ingestion workflows
- Multi-user authentication and permissions (RBAC)
- FX conversion to a configurable base currency
- Autonomous background agent runs (scheduled or event-driven)
