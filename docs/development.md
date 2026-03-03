# Development Guide

## Prerequisites

- `uv` for Python environment/dependencies
- `node` + `npm` for frontend

## First-Time Setup

```bash
cd /path/to/bill_helper
uv sync --extra dev
cd /path/to/bill_helper/frontend
npm install
```

## Version Control Hygiene

Current `.gitignore` behavior:

- ignores standard Python build/cache/test artifacts (for example `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `build/`, `dist/`, `*.egg-info/`)
- ignores local environment and secret files (for example `.env`, `.envrc`, `.venv`, `venv/`)
- ignores project runtime/frontend artifacts (`/path/to/bill_helper/frontend/node_modules/`, `/path/to/bill_helper/frontend/dist/`, `/path/to/bill_helper/.data/`, `/path/to/bill_helper/logs/`, `/path/to/bill_helper/.playwright-cli/`, `/path/to/bill_helper/output/playwright/`)

Operational impact:

- local cache/build/runtime files stay out of commits by default
- local Playwright snapshots, console/network logs, and captured browser artifacts stay out of commits by default
- `uv.lock` remains tracked unless manually ignored, matching current repository policy

## Environment Variables

All backend variables use the `BILL_HELPER_` prefix and are defined in `backend/config.py`. Runtime settings from `/api/v1/settings` take priority over env defaults where applicable.

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_APP_NAME` | `Bill Helper` | Application display name |
| `BILL_HELPER_API_PREFIX` | `/api/v1` | API route prefix |
| `BILL_HELPER_DATABASE_URL` | `sqlite:///./.data/bill_helper.db` | SQLAlchemy database URL |
| `BILL_HELPER_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `BILL_HELPER_CURRENT_USER_NAME` | `admin` | Default current user name |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | User timezone for agent date context |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency used in dashboard analytics |

### Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `openrouter/moonshotai/kimi-k2.5` | LiteLLM model identifier |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per agent run |
| `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` | `3` | Model call retry attempts |
| `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` | `0.25` | Initial retry backoff delay |
| `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` | `4.0` | Max retry backoff delay |
| `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` | `2.0` | Retry backoff multiplier |
| `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` | `5242880` | Per-attachment size limit (5 MB) |
| `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` | `4` | Max image/PDF uploads per message |

### Observability

| Variable | Default | Description |
|----------|---------|-------------|
| `LANGFUSE_PUBLIC_KEY` | _(none)_ | Enables LiteLLM Langfuse callbacks (requires secret key) |
| `LANGFUSE_SECRET_KEY` | _(none)_ | Enables LiteLLM Langfuse callbacks (requires public key) |
| `LANGFUSE_HOST` | _(Langfuse cloud)_ | Custom Langfuse host URL |

### Provider Credentials

LiteLLM resolves provider credentials from standard environment variables based on `BILL_HELPER_AGENT_MODEL`:

| Variable | Used when |
|----------|-----------|
| `OPENROUTER_API_KEY` | Model starts with `openrouter/` (default) |
| `OPENAI_API_KEY` | Model starts with `openai/` |
| `ANTHROPIC_API_KEY` | Model starts with `anthropic/` |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Model starts with `gemini/` |

### Seed / Scripts

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_SEED_CREDIT_CSV` | _(none)_ | CSV path for `scripts/seed_demo.py` (alternative to CLI arg) |

### Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Backend API base URL for Vite dev server |

### Notes

- Backend boots normally when provider credentials are missing
- Agent message execution endpoints return `503` when the configured model's provider credentials are missing
- Runtime settings from the database (`/api/v1/settings`) override env defaults for: current user name, default currency, dashboard currency, agent model, agent max steps, and retry parameters

## Database Setup

Apply migrations:

```bash
cd /path/to/bill_helper
uv run alembic upgrade head
```

Current revisions:

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
- `0017_rename_tag_category_taxonomy`
- `0018_add_tag_description`

Optional seed:

```bash
uv run python scripts/seed_demo.py /path/to/credit_card_export.csv
```

Seed behavior:

- Drops and recreates tables, then reseeds with an `admin` profile.
- Stamps Alembic revision metadata to `head` after table recreation so future `alembic upgrade head` runs stay idempotent.
- Creates demo accounts `Demo Debit` and `Demo Credit`.
- Imports credit transactions from a CSV path passed as a CLI argument or `BILL_HELPER_SEED_CREDIT_CSV` env var.
- Seeded entries default to `CAD`; currency defaults are `CAD`, `USD`, and `CNY`.
- Entities are derived from CSV transaction descriptions.
- Tag names are derived from CSV data, and tag `type` is assigned via taxonomy (`tag_type`) with values such as `transaction_type`, `merchant`, `channel`, `location`, and `payment`.

## Run Backend + Frontend Together

```bash
cd /path/to/bill_helper
./scripts/dev_up.sh
```

Behavior:

- checks for a legacy local schema state where app tables exist but `alembic_version` is missing/empty, then auto-runs `uv run alembic stamp head`
- runs `uv run alembic upgrade head` before starting services
- checks whether the `accounts` table is empty and seeds demo data only when no accounts exist
  - implementation: `scripts/dev_up.sh` calls `backend/services/bootstrap.py` (`should_seed_demo_data`) before deciding to run `scripts/seed_demo.py`
  - fresh worktree impact: first boot auto-seeds demo data into that worktree-local SQLite database
- skips demo seeding when existing accounts are present
- runs `npm install` in `frontend/` before starting services to keep UI deps in sync
- starts both processes
- writes logs in `/path/to/bill_helper/logs`
- prints service URLs
- `Ctrl+C` shuts down both

Constraints/known limitations:

- conditional auto-seeding depends on the same CSV source as manual seeding (`BILL_HELPER_SEED_CREDIT_CSV` or the script default path). If the CSV file is missing, `dev_up.sh` fails during seeding.

## Run Backend Only

```bash
cd /path/to/bill_helper
uv run bill-helper-api
```

Useful URLs:

- API: `http://localhost:8000/api/v1`
- Swagger: `http://localhost:8000/docs`
- health: `http://localhost:8000/healthz`

## Run Frontend Only

```bash
cd /path/to/bill_helper/frontend
npm run dev
```

## Verification Commands

Backend tests:

```bash
cd /path/to/bill_helper
uv run --extra dev pytest
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

## Migration Workflow

Create migration:

```bash
cd /path/to/bill_helper
uv run alembic revision -m "describe-change"
```

Apply migration:

```bash
uv run alembic upgrade head
```

## Agent + Frontend Refactor Notes

Backend agent modules:

- `backend/routers/agent.py`
- `backend/services/agent/runtime.py`
- `backend/services/agent/tools.py`
- `backend/services/agent/review.py`
- `backend/services/agent/serializers.py`

Frontend agent modules:

- coordinator: `frontend/src/components/agent/AgentPanel.tsx`
- panel presentation + local hooks: `frontend/src/components/agent/panel/*`
- run rendering: `frontend/src/components/agent/AgentRunBlock.tsx`
- run activity derivation: `frontend/src/components/agent/activity.ts`
- review modal and diff logic: `frontend/src/components/agent/review/*`

Frontend workspace modules:

- accounts: `frontend/src/features/accounts/*`, `frontend/src/pages/AccountsPage.tsx`
- properties: `frontend/src/features/properties/*`, `frontend/src/pages/PropertiesPage.tsx`

Frontend test modules:

- config/setup: `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/renderWithQueryClient.tsx`
- agent tests: `frontend/src/components/agent/activity.test.ts`, `frontend/src/components/agent/AgentRunBlock.test.tsx`, `frontend/src/components/agent/review/diff.test.ts`
- page integration tests: `frontend/src/pages/AccountsPage.test.tsx`, `frontend/src/pages/PropertiesPage.test.tsx`

Behavioral checks:

- user can open home agent workspace and create/select threads
- message send persists timeline and run history
- tool/reasoning traces appear in timeline while run is active
- proposal items can be approved/rejected individually from review modal
- accounts workspace supports create/edit/snapshot flows from split feature modules
- properties workspace supports section-specific CRUD flows from split feature modules

## Frontend Skill Workflow

Skill file:

- `/path/to/bill_helper/skills/notion-grade-ui/SKILL.md`

Current behavior:

- For frontend UI changes, agents should load and apply `notion-grade-ui`.
- The skill enforces token-only styling, primitives-first implementation, subtle interaction states, and accessibility baseline checks.
- It is not intended for backend-only work.

Operational impact:

- No new runtime dependencies or environment variables.
- Apply the skill checklist in PRs for non-trivial UI work.

Affected files/modules:

- `/path/to/bill_helper/AGENTS.md`
- `/path/to/bill_helper/skills/notion-grade-ui/SKILL.md`

Constraints:

- If existing frontend structure differs from recommended paths in the skill, adapt while preserving the same token/primitives/accessibility rules.

## Agent Import Benchmark

The `benchmark/` directory contains a framework for evaluating LLMs on bank-statement-to-entry extraction. See `benchmark/README.md` for full usage.

Quick reference:

```bash
# Reset local DB and seed default tags + entity categories
uv run python scripts/seed_defaults.py

# Create default benchmark snapshot (accounts, tags, entity categories)
uv run python -m benchmark.create_empty_snapshot

# Generate draft ground truth for a case
uv run python -m benchmark.generate_ground_truth --case my_case --model "openrouter/anthropic/claude-sonnet-4"

# Run benchmark
uv run python -m benchmark.runner --model "openrouter/google/gemini-2.5-pro" --all-cases --workers 4

# Score and compare
uv run python -m benchmark.scorer run RUN_ID
uv run python -m benchmark.scorer compare RUN_ID_1 RUN_ID_2 --save-report comparison
```

Private data (`benchmark/fixtures/`, `benchmark/results/`) is gitignored. Only `benchmark/reports/` (aggregate metrics) is tracked.

## Common Issues

## Missing provider credentials

Symptom:

- `/api/v1/agent/threads/{id}/messages` or `/api/v1/agent/threads/{id}/messages/stream` returns `503`

Fix:

- set provider credentials required by `BILL_HELPER_AGENT_MODEL` (for example `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENROUTER_API_KEY`) and restart backend

## Migration state mismatch

Symptom:

- migration errors like `table already exists`

Fix (local non-production only):

```bash
cd /path/to/bill_helper
uv run alembic stamp head
```

## Documentation Policy

Any behavior/schema/API/tooling/UI change must update:

- `README.md`
- relevant files under `/docs`

Recommended before merging:

1. `uv run --extra dev pytest`
2. `npm run build` (from `frontend/`)
3. `uv run python scripts/check_docs_sync.py`
