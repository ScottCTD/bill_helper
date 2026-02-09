# Architecture

## Goal

Bill Helper is a local-first personal finance ledger with AI-assisted, review-gated append-only change proposals.

## Runtime Topology

- Frontend SPA: React + TypeScript + Vite (`http://localhost:5173`)
- Backend API: FastAPI (`http://localhost:8000`)
- Database: SQLite (`.data/bill_helper.db`)
- Agent upload storage: local filesystem under `.data/agent_uploads`

## High-Level Components

- `frontend`: UI pages, agent panel, API calls, cache orchestration
- `backend/routers`: HTTP endpoint layer
- `backend/services`: domain logic and agent runtime/review logic
- `backend/models`: SQLAlchemy ORM tables
- `alembic`: schema migrations

## Core Decisions

- migration-first DB lifecycle via Alembic
- integer minor-unit money representation
- entry graph model with explicit link edges and derived group IDs
- soft-delete entries with link cleanup
- AI boundary is append-only proposal creation plus explicit human review apply/reject

## Backend Layering

- routers: request validation + status mapping
- services: normalization, calculations, group recomputation, agent orchestration
- models: persistence structure and relationships
- schemas: API contracts

## Agent Architecture

## Run Lifecycle

1. user sends message to `/api/v1/agent/threads/{thread_id}/messages` (text + optional images)
2. backend persists user message and attachments
3. backend creates `agent_runs` row (`running`)
4. runtime executes bounded tool-calling loop against OpenRouter
5. each tool call is persisted to `agent_tool_calls`
6. proposal tools create `agent_change_items` (`PENDING_REVIEW`)
7. runtime enforces a final assistant message and marks run `completed` or `failed`

## Review Boundary

- agent runtime cannot directly write `entries`, `tags`, `entities`
- only review endpoints apply domain mutations
- review is strictly per item (`approve` / `reject`)
- apply writes audit action rows (`agent_review_actions`)
- approved entry proposals create `entries` rows directly (no entry-level status column)

## Tooling Model (V1)

Read tools:

- `search_entries`
- `list_entries`
- `list_tags`
- `list_entities`
- `list_accounts`
- `get_dashboard_summary`

Proposal tools:

- `propose_create_entry`
- `propose_create_tag`
- `propose_create_entity`

## Agent Internal Boundaries (Refactor Baseline)

- `runtime.py`: run lifecycle orchestration and tool loop state machine
- `message_history.py`: persisted conversation/attachment conversion into LLM messages
- `model_client.py`: OpenRouter API adapter and normalized model errors
- `change_apply.py`: change-type handler registry for review-time resource application
- `review.py`: approval/rejection transitions and audit writes

## Frontend State Strategy

Remote state:

- TanStack Query for all API domains

Agent state:

- thread list query
- selected-thread detail query
- message send + approve/reject mutations

Cross-page consistency:

- approving change items invalidates ledger queries (`entries`, `tags`, `entities`, `users`, `dashboard`, `currencies`)

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
- only image attachments are accepted in agent messages
- no arbitrary code execution tools in agent runtime

## Out of Scope (Current)

- bank sync / CSV ingestion
- autonomous background agent runs
- update/delete agent proposals
- provider abstraction beyond OpenRouter integration
