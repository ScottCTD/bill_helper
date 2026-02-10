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
- Taxonomy subsystem for generalized category management:
  - shared `taxonomies` / `taxonomy_terms` / `taxonomy_assignments` tables
  - default category taxonomies for `entities` and `tags`
  - backward-compatible `entities.category` field still returned by API while sourced through taxonomy assignments
  - `PATCH /entities/{entity_id}` now resolves response category from taxonomy assignments, so term renames are reflected immediately
- React frontend with AI-native home page plus routes for dashboard, entries, entry detail, accounts, and properties.
- Dashboard analytics redesign:
  - interactive, tabbed dashboard sections (`Overview`, `Daily Spend`, `Breakdowns`, `Insights`)
  - Recharts-based plotting (bar/area/pie) instead of custom static SVG charts
  - CAD-only analytics surface (non-CAD entries are ignored in dashboard calculations)
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
  - entity dropdown now shows explicit `Create "..."` actions for unknown typed values (same pattern as tags)
  - `Tags` support typed creation for tags not yet in the system
  - newly created tag/entity values are immediately available in the current dropdown option lists
  - `Kind` now uses a single-select control and `Account` is removed from entry create/edit
  - entry table no longer includes a `Status` column/filter (status is removed from entry schema)
  - entry `Kind` table cell now renders symbol-only indicators (`+` income, `-` expense)
  - money display now uses ISO code prefix format (for example `CAD 8.13`)
- Properties UX refresh:
  - two-level navigation (`Core` / `Taxonomies`) with one active table surface at a time
  - dedicated taxonomy tables for `Entity Categories` and `Tag Categories` (name, usage, rename)
  - entities/tags category fields now use taxonomy-sourced creatable pickers
  - shared table toolbar pattern with compact right-aligned `+` add actions across `Entries` and editable `Properties` sections
- AI agent flow with review-gated proposals and per-item human review:
  - Agent can answer questions and call read tools.
  - Agent can propose CRUD changes for entries, tags, and entities (`create_*`, `update_*`, `delete_*`).
  - Entry update/delete selectors are name/date/value/from/to based and ask for user clarification on ambiguity.
  - No direct table mutation by the agent runtime.
  - Agent timeline title now surfaces model context (`Agent (<model>)`) and assistant messages render markdown content via `react-markdown` + GFM support.
  - Agent message send now returns immediately with a `running` run while execution continues in background for progressive timeline polling.
  - Composer now supports removable image chips with thumbnail previews before send.
  - Composer now supports paste (`Cmd/Ctrl+V`) and drag-drop image attachment ingestion.
  - Attachment chips are compact icon thumbnails with an extra-small corner remove (`x`) control that stays off the image preview above the chat bar.
  - Run and tool events are anchored in the assistant-side timeline with collapsible tool-call payload panels.
  - In-flight run cards no longer show `Run: running (...)` header/timestamp rows; only thinking/tool activity is shown.
  - System messages now render with markdown formatting (including list markers).
  - Thread workspace now shows one cumulative usage/cost bar above the composer (`Input`, `Output`, `Cache read`, `Cache write`, rightmost `Total cost` in USD).
  - Run costs are derived from LiteLLM model-cost mapping with OpenRouter alias support (for example `openrouter/google/gemini-3-flash-preview`).
  - Timeline run cards surface pending proposal summaries and open a dedicated unified diff review modal.
  - Review modal supports `Reject`, `Approve`, `Approve & Next`, and sequential `Approve All` flows with inline failure visibility.
  - Approved entry proposals are persisted directly to `entries` without a separate entry-level status field.
- Refactor foundation for extensibility:
  - Backend agent internals are split by concern (`prompts`, `message_history`, `model_client`, `change_apply`, `runtime`, `review`).
  - Frontend query orchestration is centralized in `frontend/src/lib/queryKeys.ts` and `frontend/src/lib/queryInvalidation.ts`.
  - Existing API contracts and route paths are unchanged.

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

- `OPENROUTER_API_KEY` (recommended; supported directly in `.env`)
- `BILL_HELPER_OPENROUTER_API_KEY` (also supported)
- `BILL_HELPER_OPENROUTER_BASE_URL` (default `https://openrouter.ai/api/v1`)
- `BILL_HELPER_AGENT_MODEL` (default `google/gemini-3-flash-preview`)
- `BILL_HELPER_AGENT_MAX_STEPS` (default `100`)
- `BILL_HELPER_DEFAULT_CURRENCY_CODE` (default `USD`)
- `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` (default `3`)
- `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` (default `0.25`)
- `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` (default `4.0`)
- `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` (default `2.0`)
- `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` (default `5242880`)
- `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` (default `4`)

Behavior when key is missing:

- app boots normally
- agent message send endpoint returns `503` with a clear configuration error

## 3) Initialize database

```bash
cd /path/to/bill_helper
uv run alembic upgrade head
uv run python scripts/seed_demo.py
```

Seed behavior:

- `scripts/seed_demo.py` resets the local database and reseeds it for user `scott`.
- after table recreation, it stamps Alembic revision metadata to `head` so subsequent `alembic upgrade head` runs stay idempotent
- Creates two accounts: `Demo Debit` and `Demo Credit`.
- Uses `CAD` as the entry currency default and configures supported defaults as `CAD`, `USD`, `CNY`.
- Imports credit-card entries from `BILL_HELPER_SEED_CREDIT_CSV`, defaulting to:
  - `path/to/your/credit_card_export.csv`
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
2. Create/select a thread.
3. Send text and optional images.
4. Review timeline:
   - user/assistant messages
   - newly sent user message appears immediately while run is in-flight
   - assistant markdown rendering with single-surface message bubbles
   - in-flight tool-call progress appears while the run is thinking
   - run/tool context is shown before final assistant message text
   - review request/action blocks appear below assistant message text
   - assistant-side run/tool-call observability with collapsible details
   - auto-refresh while the run is active
   - removable image preview chips before send
   - paste and drag-drop image attachments directly into the chat composer
   - composer shortcut: `Cmd+Enter` (or `Ctrl+Enter`) sends the message
   - single cumulative thread usage bar above the composer (`Input`, `Output`, `Cache read`, `Cache write`, rightmost `Total cost`)
   - run-level proposal summary cards with pending counts
5. Open the run review modal and process proposals:
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
- Agent services: `backend/services/agent`
- ORM models: `backend/models.py`
- Frontend app shell: `frontend/src/App.tsx`
- Frontend guide: `frontend/README.md`
- Frontend AI home page: `frontend/src/pages/HomePage.tsx`
- Frontend design tokens and component styles: `frontend/src/styles.css`
- Frontend UI primitives: `frontend/src/components/ui`
- Agent panel UI: `frontend/src/components/agent/AgentPanel.tsx`
- Latest migration: `alembic/versions/0009_remove_entry_status.py`
- Demo seed: `scripts/seed_demo.py`
