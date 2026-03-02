# Bill Helper

Bill Helper is a local-first personal billing ledger app with manual finance tracking and an AI-native home chat workspace.

## Current Status

Implemented:

- FastAPI backend with `/api/v1` endpoints for accounts, users, entries, links, groups, dashboard, entities, tags, taxonomies, currencies, and agent workflows.
- SQLite persistence with Alembic migrations:
  - `0001_initial`
  - `0002_entities_and_entry_entity_refs`
  - `0003_entity_category`
  - `0004_users_and_account_entity_links`
  - `0005_remove_attachments`
  - `0006_agent_append_only_core`
  - `0007_taxonomy_core`
  - `0008_agent_run_usage_metrics`
  - `0009_remove_entry_status`
  - `0010_runtime_settings_overrides`
  - `0011_remove_openrouter_runtime_settings_fields`
  - `0012_remove_related_link_type`
  - `0013_add_account_markdown_body`
  - `0014_remove_account_institution_type`
  - `0015_add_agent_tool_call_output_text`
  - `0016_add_user_memory_to_runtime_settings`
- Taxonomy subsystem for generalized category management:
  - shared `taxonomies` / `taxonomy_terms` / `taxonomy_assignments` tables
  - default category taxonomies for `entities` and `tags`
  - backward-compatible `entities.category` field still returned by API while sourced through taxonomy assignments
  - `PATCH /entities/{entity_id}` now resolves response category from taxonomy assignments, so term renames are reflected immediately
- React frontend with AI-native home page plus routes for dashboard, entries, entry detail, groups, accounts, properties, and settings.
- Derived group workspace:
  - dedicated `/groups` page for group summaries + graph detail
  - link-driven topology edits (create/remove links)
  - icon-only `+` link creation opens a shared modal editor in both entry detail and group workspace
  - group graph rendering uses React Flow (no bespoke graph engine)
- Runtime settings system for user-configurable defaults (persisted in DB with env fallback semantics where applicable):
  - configurable default currency and dashboard currency
  - configurable current user name used for owner/review attribution
  - optional persistent user memory text injected into every agent system prompt
  - configurable agent runtime controls (model, max steps, retry/image limits)
  - model execution is LiteLLM-based and provider-agnostic (for example OpenAI/Anthropic/Google/OpenRouter)
- Dashboard analytics redesign:
  - interactive, tabbed dashboard sections (`Overview`, `Daily Spend`, `Breakdowns`, `Insights`)
  - Recharts-based plotting (bar/area/pie) instead of custom static SVG charts
  - runtime-configured analytics currency (entries in other currencies are ignored in that dashboard response)
  - daily vs non-daily expense segmentation from tags (`daily` tag marks daily spend; `non-daily` overrides)
  - monthly projection card for current month based on spend-to-date daily pace
- Frontend UI system refactor to `shadcn/ui` + Tailwind tokens:
  - shared primitives under `frontend/src/components/ui` (Button, Card, Dialog, Input, Textarea, Table, Badge, Select foundations)
  - centralized design tokens and component-layer styles in `frontend/src/styles.css`
  - refreshed app shell/navigation and entry workflows while preserving existing API/query behavior
  - tokenized modern scrollbar treatment plus stable scrollbar gutters to reduce route/modal/table width jitter when overflow appears/disappears
- Unified popup entry editor, BlockNote markdown notes, and Notion-like tag multi-select.
- Entries UX refresh:
  - new entry creation moved to compact `+` action beside `Source text` filter
  - entry `Tag` and `Currency` filters now use chip-style multi-select controls with local row filtering for selected values
  - row double-click opens popup editor (details row action removed)
  - group column now hides unnamed UUID-style groups and only shows explicit group names
  - popup editor is a vertical, scrollable, Notion-like page with close-to-auto-save behavior
  - popup editor now uses a fixed viewport height and scrolls internally instead of expanding with long notes
  - property layout is tighter with inline `Label: control` rows
  - `Kind / Amount / Currency` now stays in a single compact row with a narrow currency-width control
  - `From / To` now uses consistent styled dropdown-combobox controls that stay aligned on one row
  - `Owner` now stays on one row in desktop popup width (with responsive wrap on small screens)
  - entity combobox inner inputs now render borderless inside the outer control to prevent overlap/double-border visuals
  - narrow currency select now sizes its wrapper (not just inner field) so the dropdown caret sits correctly next to the code
  - popup header spacing is tightened so `Date` starts closer to the title block
  - modal container now uses flex-column layout to prevent fixed-height grid row stretching gaps
  - dialog positioning no longer uses transform centering, improving editor floating-toolbar anchoring inside popup context
  - form controls only activate when clicking directly on controls (property label area no longer steals focus)
  - `From`/`To` accept typed values with suggestions and create new entities when the typed name does not exist
  - entity dropdown now shows explicit `Create entity "..."` actions for unknown typed values
  - `Tags` support typed creation for tags not yet in the system with explicit `Create tag "..."` actions
  - newly created tag/entity values are immediately available in the current dropdown option lists
  - `Kind` now uses a single-select control and `Account` is removed from entry create/edit
  - entry table no longer includes a `Status` column/filter (status is removed from entry schema)
  - entry `Kind` table cell now renders symbol-only indicators (`+` income, `-` expense)
  - money display now uses ISO code prefix format (for example `CAD 8.13`)
- Properties UX refresh:
  - two-level navigation (`Core` / `Taxonomies`) with one active table surface at a time
  - dedicated taxonomy tables for `Entity Categories` and `Tag Categories` (name, usage, rename)
  - entities/tags category fields now use taxonomy-sourced creatable pickers
  - create/edit actions for users/entities/tags/taxonomy terms are modal-driven (`+` and row `Edit`/`Rename`)
  - shared table toolbar pattern with compact right-aligned `+` add actions across `Entries` and editable `Properties` sections
- Accounts workspace now supports optional markdown notes per account (`markdown_body`) in create/edit dialogs.
- AI agent flow with review-gated proposals and per-item human review:
  - Agent can answer questions and call read tools.
  - Agent can propose CRUD changes for entries, tags, and entities (`create_*`, `update_*`, `delete_*`).
  - Entry update/delete selectors are name/date/value/from/to based and ask for user clarification on ambiguity.
  - No direct table mutation by the agent runtime.
  - Agent timeline title now surfaces model context (`Agent (<model>)`) and assistant messages render markdown content via `react-markdown` + GFM support.
  - Agent now supports real-time token streaming to the timeline via `POST /api/v1/agent/threads/{thread_id}/messages/stream` (SSE).
  - Agent can emit sparse intermediate progress notes through `send_intermediate_update`; streamed runs surface these as `reasoning_update` events.
  - Existing `POST /api/v1/agent/threads/{thread_id}/messages` behavior remains available and still starts a background run for polling-based clients.
  - Proposal tool outputs now include reusable proposal ids (`proposal_id`, `proposal_short_id`).
  - Pending proposals can be revised or removed by the agent in later turns via `update_pending_proposal` / `remove_pending_proposal` (pending-only, thread-scoped).
  - System prompt now instructs the model to batch independent tool calls in parallel when possible, instead of serial one-by-one calls.
  - If a run is interrupted, the interrupted user request remains in conversation history and the next turn is annotated so the model knows the previous response was cut short.
  - Agent system context now includes current-user account markdown notes (`notes_markdown`) with truncation safeguards for oversized markdown/data-url image payloads.
  - Composer now supports removable attachment chips (image thumbnails + PDF file chips) before send.
  - Composer now supports paste (`Cmd/Ctrl+V`) and drag-drop image/PDF attachment ingestion.
  - Agent message uploads now accept PDF attachments in addition to images.
  - PDF attachments are parsed with PyMuPDF text extraction (line-trimmed + whitespace-normalized); extracted text is appended to model input, and when the configured model supports vision each PDF page is also sent as an image.
  - Attachment chips are compact icon thumbnails with an extra-small corner remove (`x`) control that stays off the image preview above the chat bar.
  - Run and tool events are anchored in the assistant-side timeline with collapsible tool-call payload panels.
  - Runs interleave reasoning updates and grouped tool-call batches in both active and completed states for a consistent trace view.
  - In-flight run cards no longer show `Run: running (...)` header/timestamp rows; only thinking/tool activity is shown.
  - System messages now render with markdown formatting (including list markers).
  - Thread workspace now shows one cumulative usage/cost bar above the composer (`Context`, `Input`, `Output`, `Cache read`, `Cache hit rate`, rightmost `Total cost` in USD), with token metrics compacted as `x.xxK`.
  - Run costs are derived from LiteLLM model-cost mapping using the configured model name.
  - Timeline run cards surface pending proposal summaries and open a dedicated unified diff review modal.
  - Review modal supports `Reject`, `Approve`, `Approve All`, and `Reject All` flows with inline failure visibility.
  - Review diff rows now use friendly field labels/order and human-readable amount values.
  - Tool-call details now prioritize model-visible tool output text and keep structured JSON as secondary debug data.
  - Approved entry proposals are persisted directly to `entries` without a separate entry-level status field.
  - LiteLLM request payloads now explicitly inject prompt-caching breakpoints (`cache_control_injection_points`) anchored to system context and latest user turn (negative message index) for models that support prompt caching.
- Refactor foundation for extensibility:
  - Backend agent internals are split by concern (`prompts`, `message_history`, `model_client`, `change_apply`, `runtime`, `review`).
  - Frontend query orchestration is centralized in `frontend/src/lib/queryKeys.ts` and `frontend/src/lib/queryInvalidation.ts`.
  - Accounts and properties workspaces follow feature-module boundaries (thin page orchestrator + domain hooks + section components).
  - Properties model internals are split into dedicated hooks for queries, UI section state, form state, and filtered views.
  - Agent panel rendering concerns are split into panel modules (`frontend/src/components/agent/panel/*`) and attachment/composer helper hooks.
  - Frontend test coverage includes page-level integration tests for accounts/properties in addition to agent rendering/diff helpers.
  - Existing API contracts remain compatible, with an added agent SSE stream endpoint for incremental assistant text.

Deferred:

- Live bank sync and generalized multi-bank CSV ingestion workflows.
- Multi-user auth/permissions.
- FX conversion to base currency.

## Architecture Snapshot

- Frontend: React + TypeScript + Vite + Tailwind + `shadcn/ui` primitives (`/frontend`)
- Backend: FastAPI + SQLAlchemy + Pydantic (`/backend`)
- Database: SQLite (`.data/bill_helper.db`)
- Migrations: Alembic (`/alembic`)
- Python dependency management: `uv`
- Project agent skills: `notion-grade-ui` for frontend UI work (`/skills/notion-grade-ui/SKILL.md`)

## Documentation Map

Primary docs are in `docs/`:

- `docs/README.md`
- `docs/architecture.md`
- `docs/repository-structure.md`
- `docs/backend.md`
- `docs/frontend.md`
- `docs/api.md`
- `docs/data-model.md`
- `docs/development.md`
- `docs/documentation-system.md`
- `docs/feature-entry-lifecycle.md`
- `docs/feature-dashboard-analytics.md`
- `docs/feature-account-reconciliation.md`
- `docs/adr/README.md`

## Quick Start

## 1) Install dependencies

```bash
cd /path/to/bill_helper
uv sync --extra dev
cd frontend
npm install
```

## 2) Configure agent runtime (optional but required for agent message runs)

Set these environment variables (for example in `.env`):

- `LANGFUSE_PUBLIC_KEY` (optional; enables LiteLLM Langfuse callback tracing when paired with secret key)
- `LANGFUSE_SECRET_KEY` (optional; enables LiteLLM Langfuse callback tracing when paired with public key)
- `LANGFUSE_HOST` (optional; default Langfuse cloud host is `https://cloud.langfuse.com`)
- `BILL_HELPER_AGENT_MODEL` (default `openrouter/moonshotai/kimi-k2.5`)
- `BILL_HELPER_AGENT_MAX_STEPS` (default `100`)
- `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` (default `America/Toronto`; controls system-prompt current date context)
- `BILL_HELPER_DEFAULT_CURRENCY_CODE` (default `CAD`)
- `BILL_HELPER_DASHBOARD_CURRENCY_CODE` (default `CAD`)
- `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` (default `3`)
- `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` (default `0.25`)
- `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` (default `4.0`)
- `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` (default `2.0`)
- `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` (default `5242880`; per-attachment size limit for image/PDF agent uploads)
- `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` (default `4`; max image/PDF uploads per agent message)

Provider credential behavior:

- LiteLLM resolves credentials directly from provider environment variables for the selected `BILL_HELPER_AGENT_MODEL`
- examples:
  - `OPENAI_API_KEY` with `BILL_HELPER_AGENT_MODEL=openai/gpt-4.1-mini`
  - `ANTHROPIC_API_KEY` with `BILL_HELPER_AGENT_MODEL=anthropic/claude-3-5-sonnet-20240620`
  - `OPENROUTER_API_KEY` with `BILL_HELPER_AGENT_MODEL=openrouter/moonshotai/kimi-k2.5` (default)

Observability behavior:

- when `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, runtime enables LiteLLM `langfuse` success/failure callbacks
- each model call includes LiteLLM metadata (`trace_id`, `session_id`, `trace_user_id`, `generation_name`) so runs in one thread stay grouped in Langfuse

Behavior when credentials are missing:

- app boots normally
- agent message send endpoint returns `503` with a clear configuration error for the resolved model target

## 3) Initialize database

```bash
cd /path/to/bill_helper
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

Seed behavior:

- `scripts/seed_demo.py` resets the local database and reseeds it with an `admin` user profile.
- after table recreation, it stamps Alembic revision metadata to `head` so subsequent `alembic upgrade head` runs stay idempotent
- Creates two demo accounts: `Demo Debit` and `Demo Credit`.
- Uses `CAD` as the entry currency default and configures supported defaults as `CAD`, `USD`, `CNY`.
- Imports credit-card entries from a CSV path passed as a CLI argument (or `BILL_HELPER_SEED_CREDIT_CSV` env var).
- Derives entry counterparties (`entities`) from CSV transaction descriptions.
- Derives clean tag names from CSV fields and writes semantic tag categories via taxonomy (`tag_category`), including `transaction_type`, `merchant`, `channel`, `location`, and `payment`.

## 4) Run backend + frontend together (recommended)

```bash
cd /path/to/bill_helper
./scripts/dev_up.sh
```

Behavior:

- checks whether app tables exist without Alembic revision metadata (missing/empty `alembic_version`) and runs `uv run alembic stamp head` to repair local migration state
- runs `uv run alembic upgrade head` before boot so tables exist on fresh/local DBs
- checks whether `accounts` is empty and runs `uv run python scripts/seed_demo.py` only when no accounts exist (for example, a new worktree database)
- skips demo seeding when at least one account already exists
- runs `npm install` in `frontend/` before boot so frontend dependencies stay synchronized
- starts backend and frontend together
- writes logs to `logs/`
- prints frontend/backend URLs
- `Ctrl+C` stops both

Operational note:

- auto-seeding still requires a valid credit CSV (`BILL_HELPER_SEED_CREDIT_CSV` or the script default path); if missing, startup fails during the seed step.

## 5) Run backend only

```bash
cd /path/to/bill_helper
uv run bill-helper-api
```

Backend URLs:

- API base: `http://localhost:8000/api/v1`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/healthz`

## 6) Run frontend only

```bash
cd /path/to/bill_helper/frontend
npm run dev
```

Frontend URL:

- `http://localhost:5173`

## Agent UX Quick Path

1. Open the app and use the `Home` route for the AI-native chat workspace.
2. Use `Settings` to configure runtime defaults (currency/model/step and key fallback behavior) before running agent-heavy workflows if needed.
3. Create/select a thread.
4. Send text and optional attachments (images or PDFs).
5. Review timeline:
   - user/assistant messages
   - newly sent user message appears immediately while run is in-flight
   - assistant markdown rendering with single-surface message bubbles
   - in-flight tool-call progress appears while the run is thinking
   - run/tool context is shown before final assistant message text
   - review request/action blocks appear below assistant message text
   - assistant-side run/tool-call observability with collapsible details
   - auto-refresh while the run is active
   - removable attachment chips before send
   - paste and drag-drop image/PDF attachments directly into the chat composer
   - composer shortcut: `Cmd+Enter` (or `Ctrl+Enter`) sends the message
   - single cumulative thread usage bar above the composer (`Context`, `Input`, `Output`, `Cache read`, `Cache hit rate`, rightmost `Total cost`)
   - run-level proposal summary cards with pending counts
6. Open the run review modal and process proposals:
   - entry proposals support JSON edit-before-approve with unified payload diff
   - use `Approve & Next` for focused step-through review
   - use `Approve All` for deterministic sequential batch apply (with partial-failure summary/jump links)

## Verification Commands

Backend tests:

```bash
cd /path/to/bill_helper
uv run pytest
```

Frontend build:

```bash
cd /path/to/bill_helper/frontend
npm run build
```

Frontend tests:

```bash
cd /path/to/bill_helper/frontend
npm run test
```

Migration state:

```bash
cd /path/to/bill_helper
uv run alembic current
```

Documentation consistency:

```bash
cd /path/to/bill_helper
uv run python scripts/check_docs_sync.py
```

## Key Paths

- Backend app: `backend/main.py`
- Backend guide: `backend/README.md`
- Agent router: `backend/routers/agent.py`
- Settings router: `backend/routers/settings.py`
- Agent services: `backend/services/agent`
- Runtime settings resolver: `backend/services/runtime_settings.py`
- ORM models: `backend/models.py`
- Frontend app shell: `frontend/src/App.tsx`
- Frontend guide: `frontend/README.md`
- Frontend AI home page: `frontend/src/pages/HomePage.tsx`
- Frontend groups page: `frontend/src/pages/GroupsPage.tsx`
- Frontend agent panel modules: `frontend/src/components/agent/panel`
- Frontend settings page: `frontend/src/pages/SettingsPage.tsx`
- Frontend accounts feature modules: `frontend/src/features/accounts`
- Frontend properties feature modules: `frontend/src/features/properties`
- Frontend design tokens and component styles: `frontend/src/styles.css`
- Frontend UI primitives: `frontend/src/components/ui`
- Agent panel UI: `frontend/src/components/agent/AgentPanel.tsx`
- Latest migration: `alembic/versions/0016_add_user_memory_to_runtime_settings.py`
- Demo seed: `scripts/seed_demo.py`
