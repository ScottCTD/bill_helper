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
- ignores project runtime/frontend artifacts (`/path/to/bill_helper/frontend/node_modules/`, `/path/to/bill_helper/frontend/dist/`, `/path/to/bill_helper/.data/`, `/path/to/bill_helper/logs/`)

Operational impact:

- local cache/build/runtime files stay out of commits by default
- `uv.lock` remains tracked unless manually ignored, matching current repository policy

## Environment Variables

Supported variables (prefix `BILL_HELPER_`):

Core:

- `APP_NAME`
- `API_PREFIX`
- `DATABASE_URL`
- `CORS_ORIGINS`
- `CURRENT_USER_NAME`
- `DASHBOARD_CURRENCY_CODE`

Agent:

- `OPENROUTER_API_KEY` (recommended)
- `BILL_HELPER_OPENROUTER_API_KEY` (also accepted)
- `OPENROUTER_BASE_URL`
- `AGENT_MODEL`
- `AGENT_MAX_STEPS` (default `100`)
- `DEFAULT_CURRENCY_CODE` / `BILL_HELPER_DEFAULT_CURRENCY_CODE` (default `CAD`)
- `DASHBOARD_CURRENCY_CODE` / `BILL_HELPER_DASHBOARD_CURRENCY_CODE` (default `CAD`)
- `AGENT_RETRY_MAX_ATTEMPTS` (default `3`)
- `AGENT_RETRY_INITIAL_WAIT_SECONDS` (default `0.25`)
- `AGENT_RETRY_MAX_WAIT_SECONDS` (default `4.0`)
- `AGENT_RETRY_BACKOFF_MULTIPLIER` (default `2.0`)
- `AGENT_MAX_IMAGE_SIZE_BYTES`
- `AGENT_MAX_IMAGES_PER_MESSAGE`

Notes:

- backend boots without `OPENROUTER_API_KEY`
- runtime behavior resolves settings from `/api/v1/settings` overrides first, then env defaults
- agent message execution endpoints return `503` only when both user override key and server default key are missing

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

Optional seed:

```bash
uv run python scripts/seed_demo.py
```

Seed behavior:

- Drops and recreates tables, then reseeds with a `scott` profile.
- Stamps Alembic revision metadata to `head` after table recreation so future `alembic upgrade head` runs stay idempotent.
- Creates accounts `Demo Debit` and `Demo Credit`.
- Imports demo credit transactions from CSV path `BILL_HELPER_SEED_CREDIT_CSV` (default `path/to/your/credit_card_export.csv`).
- Seeded entries default to `CAD`; currency defaults are `CAD`, `USD`, and `CNY`.
- Entities are derived from CSV transaction descriptions.
- Tag names are derived from CSV data, and tag `category` is assigned via taxonomy (`tag_category`) with values such as `transaction_type`, `merchant`, `channel`, `location`, and `payment`.

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

## Agent Feature Dev Notes

Affected backend modules:

- `backend/routers/agent.py`
- `backend/services/agent/runtime.py`
- `backend/services/agent/tools.py`
- `backend/services/agent/review.py`
- `backend/services/agent/serializers.py`

Affected frontend modules:

- `frontend/src/components/agent/AgentPanel.tsx`
- `frontend/src/App.tsx`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/styles.css`

Behavioral checks:

- user can open panel globally and create/select threads
- message send persists timeline and run history
- tool traces appear in timeline
- proposal items can be approved/rejected individually
- approving entry proposals creates entry rows directly (no entry-level status column)

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

## Common Issues

## Missing OpenRouter key

Symptom:

- `/api/v1/agent/threads/{id}/messages` returns `503`

Fix:

- set `OPENROUTER_API_KEY` (or `BILL_HELPER_OPENROUTER_API_KEY`) and restart backend

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
