# Development Guide

## Prerequisites

- `uv` for Python environment/dependencies
- `node` + `npm` for frontend
- `tesseract` (optional, but required if you want OCR fallback for image-only/redacted PDF uploads in the agent)

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
- ignores local desloppify scan artifacts (`/path/to/bill_helper/.desloppify/`, `/path/to/bill_helper/scorecard.png`)

Operational impact:

- local cache/build/runtime files stay out of commits by default
- local Playwright snapshots, console/network logs, and captured browser artifacts stay out of commits by default
- local desloppify state/query snapshots and scorecards stay out of commits by default
- `uv.lock` remains tracked unless manually ignored, matching current repository policy

## Environment Variables

All backend variables use the `BILL_HELPER_` prefix and are defined in `backend/config.py`. Runtime settings from `/api/v1/settings` take priority over env defaults where applicable.

### Env File Cascade

Configuration is resolved in this order (highest → lowest priority):

| Priority | Source | Purpose |
|----------|--------|---------|
| 1 | Real environment variables | Production / CI (platform-injected) |
| 2 | `.env` in working directory | Per-worktree overrides (gitignored) |
| 3 | `~/.config/bill-helper/.env` | Shared dev secrets across all worktrees |
| 4 | Defaults in `backend/config.py` | Sensible fallbacks |

This means secrets like `OPENROUTER_API_KEY` or `AWS_BEARER_TOKEN_BEDROCK` only need to be configured once in the shared location and are available to every worktree automatically. Bill Helper mirrors env-file variables into the process environment before LiteLLM validation and model calls, so provider-specific SDK/env lookups see the same shared secrets. A per-worktree `.env` can selectively override any value (e.g., test a different model).

### Shared Data Directory

Application data (SQLite DB) defaults to `~/.local/share/bill-helper/`, following XDG conventions. This means all worktrees share the same database — no need to re-migrate or re-seed per worktree.

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `BILL_HELPER_DATABASE_URL` | Explicit DB URL (e.g., PostgreSQL in prod) |
| 2 | `BILL_HELPER_DATA_DIR` | Custom data dir → DB path derived automatically |
| 3 | Default | `~/.local/share/bill-helper/bill_helper.db` |

To use a per-worktree isolated database (e.g., for testing a migration), set in your local `.env`:

```
BILL_HELPER_DATA_DIR=./.data
```

#### First-time shared env setup

```bash
# Option A: copy your existing .env to the shared location
./scripts/setup_shared_env.sh

# Option B: create a blank template to fill in
./scripts/setup_shared_env.sh --clean
```

#### Git worktree workflow

```bash
git worktree add ../bill_helper-feature feature-branch
cd ../bill_helper-feature
uv sync --extra dev
# Shared secrets from ~/.config/bill-helper/.env are already available.
# Optionally create a local .env for worktree-specific overrides.
```

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_APP_NAME` | `Bill Helper` | Application display name |
| `BILL_HELPER_API_PREFIX` | `/api/v1` | API route prefix |
| `BILL_HELPER_DATA_DIR` | `~/.local/share/bill-helper` | Shared data directory (SQLite DB lives here) |
| `BILL_HELPER_DATABASE_URL` | _(derived from data_dir)_ | SQLAlchemy database URL; overrides data_dir for DB |
| `BILL_HELPER_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `BILL_HELPER_CURRENT_USER_NAME` | `admin` | Default current user name |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | User timezone for agent date context |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency used in dashboard analytics |

### Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `bedrock/us.anthropic.claude-sonnet-4-6` | LiteLLM model identifier |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per agent run |
| `BILL_HELPER_AGENT_BULK_MAX_CONCURRENT_THREADS` | `4` | Max fresh threads Bulk mode starts at once |
| `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` | `3` | Model call retry attempts |
| `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` | `0.25` | Initial retry backoff delay |
| `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` | `4.0` | Max retry backoff delay |
| `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` | `2.0` | Retry backoff multiplier |
| `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` | `5242880` | Per-attachment size limit (5 MB) |
| `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` | `4` | Max image/PDF uploads per message |

### Provider Credentials

LiteLLM resolves provider credentials from standard environment variables based on `BILL_HELPER_AGENT_MODEL`. Bill Helper forwards only explicit app-level overrides through `AGENT_API_KEY` / `AGENT_BASE_URL` (or the matching runtime settings override fields).

| Variable | Used when |
|----------|-----------|
| `AWS_BEARER_TOKEN_BEDROCK` or standard AWS Bedrock credential env vars | Model starts with `bedrock/` (default) |
| `OPENROUTER_API_KEY` | Model starts with `openrouter/` |
| `OPENAI_API_KEY` | Model starts with `openai/` |
| `ANTHROPIC_API_KEY` | Model starts with `anthropic/` |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Model starts with `gemini/` |
| `AGENT_API_KEY` / `BILL_HELPER_AGENT_API_KEY` | Explicit app-level credential override for a custom endpoint |
| `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL` | Explicit app-level base URL override for a custom endpoint |

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
- `GET /settings` reports `agent_api_key_configured=true` when either an explicit override key exists or LiteLLM can resolve provider credentials for the selected model; `agent_base_url` reflects only explicit overrides
- Runtime settings from the database (`/api/v1/settings`) override env defaults for: current user name, default currency, dashboard currency, agent model, ordered available agent models, agent max steps, Bulk mode concurrency, and retry parameters

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
- `0019_add_transfer_entry_kind`
- `0020_add_agent_message_attachment_original_filename`
- `0021_add_agent_run_context_tokens`
- `0022_agent_run_events_and_tool_lifecycle`
- `0023_add_agent_provider_config`
- `0024_entity_root_accounts`
- `0025_user_memory_json_list`
- `0027_add_agent_bulk_concurrency_setting`

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

## Run Telegram Bot (Local Dev Polling)

Required env/config:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_BACKEND_BASE_URL` (defaults to `http://localhost:8000/api/v1`)
- `TELEGRAM_API_BASE_URL` (optional override; defaults to `https://api.telegram.org`)
- `TELEGRAM_DATA_DIR` (optional; defaults to `~/.local/share/bill-helper/telegram`)
- `TELEGRAM_STATE_PATH` (optional; defaults to `<TELEGRAM_DATA_DIR>/chat_state.json`)
- backend auth for the bot via either `TELEGRAM_BACKEND_AUTH_TOKEN` or `TELEGRAM_BACKEND_AUTH_HEADERS`

Notes:

- `TELEGRAM_BACKEND_AUTH_HEADERS` must be a JSON object of header names to values.
- If both `TELEGRAM_BACKEND_AUTH_TOKEN` and an explicit `Authorization` header are supplied, the explicit header wins.

Run the polling worker:

```bash
cd /path/to/bill_helper
uv run python -m telegram.polling
```

The polling worker uses a `python-telegram-bot` application with PTB command handlers plus a private-chat message handler that forwards non-command traffic into the shared Telegram content handler.

Because this repository also has a top-level `telegram/` package, bot modules should import PTB symbols from `telegram.ptb`, not directly from the upstream `telegram` package. `telegram/ptb.py` bootstraps the installed `python-telegram-bot` distribution and re-exports the PTB types used inside this codebase.

## Run Telegram Webhook Adapter

Required env/config:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_BACKEND_BASE_URL` (defaults to `http://localhost:8000/api/v1`)
- `TELEGRAM_API_BASE_URL` (optional override; defaults to `https://api.telegram.org`)
- `TELEGRAM_DATA_DIR` (optional; defaults to `~/.local/share/bill-helper/telegram`)
- `TELEGRAM_STATE_PATH` (optional; defaults to `<TELEGRAM_DATA_DIR>/chat_state.json`)
- backend auth for the bot via either `TELEGRAM_BACKEND_AUTH_TOKEN` or `TELEGRAM_BACKEND_AUTH_HEADERS`

Run the webhook app locally:

```bash
cd /path/to/bill_helper
uv run python -m telegram.webhook
```

The webhook app listens on port `8081`, serves `GET /healthz`, validates `X-Telegram-Bot-Api-Secret-Token` on `POST /telegram/webhook`, and then hands the JSON payload to the PTB application for command/message routing.

## Verification Commands

Backend tests:

```bash
cd /path/to/bill_helper
uv run --extra dev pytest
```

Telegram transport compile check:

```bash
cd /path/to/bill_helper
uv run --extra dev python -m py_compile telegram/__init__.py telegram/bill_helper_api.py telegram/commands.py telegram/config.py telegram/files.py telegram/formatting.py telegram/message_handler.py telegram/polling.py telegram/ptb.py telegram/state.py telegram/webhook.py
```

Backend + Telegram transport tests:

```bash
cd /path/to/bill_helper
OPENROUTER_API_KEY=test uv run --extra dev pytest backend/tests telegram/tests -q
```

Backend performance guard tests:

```bash
cd /path/to/bill_helper
uv run --extra dev pytest backend/tests/test_agent_performance.py
```

Frontend build:

```bash
cd /path/to/bill_helper/frontend
npm run build
npm audit
```

Frontend tests:

```bash
cd /path/to/bill_helper/frontend
npm run test
```

iOS shell + API tests:

```bash
cd /path/to/bill_helper
xcodebuild -project ios/BillHelperApp.xcodeproj -scheme BillHelperApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:BillHelperAPITests test
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
- `backend/services/agent/runtime_state.py`
- `backend/services/agent/run_orchestrator.py`
- `backend/services/agent/message_history.py`
- `backend/services/agent/attachment_content.py`
- `backend/services/agent/user_context.py`
- `backend/services/agent/protocol_helpers.py`
- `backend/services/agent/tool_args.py`
- `backend/services/agent/tool_handlers_read.py`
- `backend/services/agent/tool_handlers_propose.py`
- `backend/services/agent/proposal_patching.py`
- `backend/services/agent/tool_runtime.py`
- `backend/services/agent/tools.py` (thin facade)
- `backend/services/agent/review.py`
- `backend/services/agent/serializers.py`

Architecture quality baseline:

- follow `AGENTS.md` for anti-slop ownership boundaries and required refactor/test/doc gates

Frontend agent modules:

- coordinator: `frontend/src/features/agent/AgentPanel.tsx`
- panel presentation + local hooks: `frontend/src/features/agent/panel/*`
- run rendering: `frontend/src/features/agent/AgentRunBlock.tsx`
- run activity derivation: `frontend/src/features/agent/activity.ts`
- review modal and diff logic: `frontend/src/features/agent/review/*`

Frontend workspace modules:

- accounts: `frontend/src/features/accounts/*`, `frontend/src/pages/AccountsPage.tsx`
- properties: `frontend/src/features/properties/*`, `frontend/src/pages/PropertiesPage.tsx`

Frontend test modules:

- config/setup: `frontend/vitest.config.ts`, `frontend/src/test/setup.ts`, `frontend/src/test/renderWithQueryClient.tsx`
- agent tests: `frontend/src/features/agent/activity.test.ts`, `frontend/src/features/agent/AgentRunBlock.test.tsx`, `frontend/src/features/agent/review/diff.test.ts`
- page integration tests: `frontend/src/pages/AccountsPage.test.tsx`, `frontend/src/pages/PropertiesPage.test.tsx`

Behavioral checks:

- user can open home agent workspace and create/select threads
- message send persists timeline and run history
- tool/reasoning traces appear in timeline while run is active
- proposal items can be approved/rejected individually from the thread review modal
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

## Desloppify Skill Workflow

Skill file:

- `/path/to/bill_helper/skills/desloppify-maintenance/SKILL.md`

Current behavior:

- For explicit desloppify cleanup requests, agents should load and apply `desloppify-maintenance`.
- The skill makes `uv run desloppify ...` the default entrypoint, keeps the tool queue as the source of truth, and requires recording durable fix batches in dated fix-log docs under `docs/exec-plans/completed/`.
- It is not the default for ordinary feature work that does not use the desloppify workflow.

Operational impact:

- Before scanning, review generated/runtime/vendor/build directories and exclude only obvious non-source paths directly; questionable exclude candidates must be surfaced to the user first.
- Typical commands are `uv run desloppify scan --path .`, `uv run desloppify next`, the printed `uv run desloppify resolve ...` command for each completed item, and periodic `uv run desloppify plan` / `scan` refreshes when the queue shifts.
- Behavior, schema, or tooling fixes that come out of the queue must still pass the repository verification gates, including `OPENROUTER_API_KEY=test uv run --extra dev pytest backend/tests -q` and `uv run python scripts/check_docs_sync.py`.

Affected files/modules:

- `/path/to/bill_helper/AGENTS.md`
- `/path/to/bill_helper/skills/desloppify-maintenance/SKILL.md`
- `/path/to/bill_helper/docs/exec-plans/completed/2026-03-05_clean_architecture_fix_log.md`

Constraints:

- Do not treat desloppify as a cosmetic scoring game; resolve root causes, not just surface findings.
- Keep local desloppify state such as `.desloppify/` and `scorecard.png` out of commits unless the user explicitly asks to track them.

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

### Missing provider credentials

Symptom:

- `/api/v1/agent/threads/{id}/messages` or `/api/v1/agent/threads/{id}/messages/stream` returns `503`

Fix:

- set provider credentials required by `BILL_HELPER_AGENT_MODEL` (for example `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENROUTER_API_KEY`) in `~/.config/bill-helper/.env` and restart backend

### Migration state mismatch

Symptom:

- migration errors like `table already exists`

Fix (local non-production only):

```bash
cd /path/to/bill_helper
uv run alembic stamp head
```

## Documentation Policy

Use the layered doc system:

- `README.md` for onboarding and the dev loop.
- `AGENTS.md` for short agent instructions and doc pointers.
- `docs/*.md` for stable index docs and cross-cutting reference docs.
- `docs/backend/*.md`, `docs/frontend/*.md`, and `docs/api/*.md` for focused subsystem reference docs.
- `docs/exec-plans/active/*.md` for active implementation plans and temporary caveats.
- `docs/exec-plans/completed/*.md` for archived plans and retrospectives.

Any behavior, schema, API, tooling, or UI change must update the relevant stable docs in the canonical docs tree. Use execution plans for work tracking, not as the final source of truth.

Recommended before merging:

1. `uv run --extra dev pytest`
2. `npm run build` (from `frontend/`)
3. `uv run python scripts/check_docs_sync.py`
