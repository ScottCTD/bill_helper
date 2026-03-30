# Development Guide

## Prerequisites

- `uv` for Python environment, scripts, and tests
- `node` + `npm` for the frontend
- `docker` for the default agent-workspace provisioning flow and Docker-backed workspace tests
- Docling + EasyOCR run on the API host for agent PDF/image uploads (first Docling use may download models); ensure typical PyTorch/OpenCV system libraries are available in your environment if conversion fails at import or runtime

## First-Time Setup

```bash
cd /path/to/bill_helper
uv sync
cd frontend
npm install
cd ..
```

## Environment Resolution

All backend variables use the `BILL_HELPER_` prefix and are defined in `backend/config.py`.

Configuration resolves in this order:

1. real environment variables
2. `.env` in the working directory
3. `~/.config/bill-helper/.env`
4. defaults in code

Shared secrets and shared data therefore work across Git worktrees by default.

### Shared Data Directory

Application data defaults to `~/.local/share/bill_helper/`.

- default SQLite path: `~/.local/share/bill_helper/bill_helper.db`
- canonical user-visible files: `~/.local/share/bill_helper/user_files/{user_id}/uploads`
- override with `BILL_HELPER_DATABASE_URL`
- or override the root directory with `BILL_HELPER_DATA_DIR`

For a per-worktree database:

```env
BILL_HELPER_DATA_DIR=./.data
```

## Core Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_APP_NAME` | `Bill Helper` | Application display name |
| `BILL_HELPER_API_PREFIX` | `/api/v1` | API route prefix |
| `BILL_HELPER_DATA_DIR` | `~/.local/share/bill_helper` | Shared data directory |
| `BILL_HELPER_DATABASE_URL` | _(derived from data dir)_ | SQLAlchemy database URL |
| `BILL_HELPER_CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed CORS origins |
| `CURRENT_USER_TIMEZONE` | `America/Toronto` | Timezone for agent date context |
| `BILL_HELPER_DEFAULT_CURRENCY_CODE` | `CAD` | Default currency for new entries |
| `BILL_HELPER_DASHBOARD_CURRENCY_CODE` | `CAD` | Currency used in dashboard analytics |

## Agent Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `BILL_HELPER_AGENT_MODEL` | `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0` | LiteLLM model identifier |
| `BILL_HELPER_AGENT_MAX_STEPS` | `100` | Max tool-call steps per run |
| `BILL_HELPER_AGENT_BULK_MAX_CONCURRENT_THREADS` | `4` | Max fresh threads Bulk mode starts at once |
| `BILL_HELPER_AGENT_RETRY_MAX_ATTEMPTS` | `3` | Model call retry attempts |
| `BILL_HELPER_AGENT_RETRY_INITIAL_WAIT_SECONDS` | `0.25` | Initial retry backoff delay |
| `BILL_HELPER_AGENT_RETRY_MAX_WAIT_SECONDS` | `4.0` | Max retry backoff delay |
| `BILL_HELPER_AGENT_RETRY_BACKOFF_MULTIPLIER` | `2.0` | Retry backoff multiplier |
| `BILL_HELPER_AGENT_MAX_IMAGE_SIZE_BYTES` | `5242880` | Per-attachment size limit |
| `BILL_HELPER_AGENT_MAX_IMAGES_PER_MESSAGE` | `4` | Max image/PDF uploads per message |
| `BILL_HELPER_AGENT_WORKSPACE_ENABLED` | `true` | Enable eager per-user Docker workspace provisioning |
| `BILL_HELPER_AGENT_WORKSPACE_IMAGE` | `bill-helper-agent-workspace:latest` | Prebuilt image tag for per-user workspaces |
| `BILL_HELPER_AGENT_WORKSPACE_DOCKER_BINARY` | `docker` | Docker CLI binary used for workspace lifecycle commands |
| `BILL_HELPER_WORKSPACE_BACKEND_BASE_URL` | `http://host.docker.internal:8000/api/v1` | Backend API base URL used by workspace terminal commands and the installed `bh` CLI |
| `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL` | _(none)_ | Optional custom provider endpoint |
| `AGENT_API_KEY` / `BILL_HELPER_AGENT_API_KEY` | _(none)_ | Optional custom provider API key |

## Agent Workspace Provisioning

The backend now provisions one deterministic workspace definition per user:

- host files: `{data_dir}/user_files/{user_id}/uploads`
- named volume: `bill-helper-workspace-{user_id}`
- named container: `bill-helper-sandbox-{user_id}`
- mounts: `/workspace/uploads` read-only from the user's canonical uploads and `/workspace` from the named volume

Build the local image before running admin bootstrap or creating users through the admin API:

```bash
docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .
```

Behavior notes:

- the backend does not auto-build this image
- when workspace provisioning is enabled, admin bootstrap and user creation fail with a provisioning error if the configured image tag is missing
- set `BILL_HELPER_AGENT_WORKSPACE_ENABLED=0` in environments where you intentionally do not want Docker-backed provisioning
- if the backend itself runs inside Docker, it still needs host-daemon access through `/var/run/docker.sock` or `DOCKER_HOST` to manage sibling user workspaces

Workspace refresh notes:

- The workspace image is built from the checked-out repo and installs `bill-helper` during `docker build`; running sandbox containers do not see later source edits automatically.
- Rebuild the image after changes to files copied into `docker/agent-workspace.dockerfile`, especially `backend/`, `telegram/`, `pyproject.toml`, `README.md`, `docker/agent-workspace.dockerfile`, or `docker/agent-workspace-entrypoint.sh`.
- Recreate any running `bill-helper-sandbox-*` containers after that rebuild so the backend launches new workspaces from the new image. This refresh keeps the named workspace volume unless you remove it separately.
- When the changed behavior affects installed workspace tools such as `bh`, verify the result from inside a fresh sandbox container instead of only running the command from the host checkout.

Refresh workflow:

```bash
docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .
for name in $(docker ps --format '{{.Names}}' | grep '^bill-helper-sandbox-'); do
  docker rm -f "$name"
done
```

## Provider Credentials

LiteLLM resolves provider credentials from environment variables based on the selected model.

| Variable | Used when |
|----------|-----------|
| `AWS_BEARER_TOKEN_BEDROCK` or standard AWS Bedrock env vars | model starts with `bedrock/` |
| `OPENROUTER_API_KEY` | model starts with `openrouter/` |
| `OPENAI_API_KEY` | model starts with `openai/` |
| `ANTHROPIC_API_KEY` | model starts with `anthropic/` |
| `GOOGLE_API_KEY` / `GEMINI_API_KEY` | model starts with `gemini/` |

Backend startup succeeds without provider credentials; only agent execution fails (`503`) until a valid credential source exists.

## Auth Bootstrap

After migrating an existing database, create or reset an admin password explicitly:

```bash
uv run python scripts/bootstrap_admin.py --name admin --password admin
```

Behavior:

- upgrades the database to head if needed
- creates the named user when absent
- resets the password and ensures `is_admin=true` when the user already exists

The backend uses password-backed bearer sessions for protected routes and the web app.

## Database Setup

Apply migrations:

```bash
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
- `0026_entry_groups_v2`
- `0027_add_agent_bulk_concurrency_setting`
- `0028_add_available_agent_models_to_runtime_settings`
- `0029_add_agent_run_surface`
- `0030_add_account_agent_change_types`
- `0031_add_user_is_admin`
- `0032_add_filter_groups`
- `0033_multi_user_security`
- `0034_add_entry_tagging_model_to_runtime_settings`
- `0035_add_user_files_and_agent_workspace`

## Seed Data

Optional demo seed:

```bash
uv run python scripts/seed_demo.py /path/to/credit_card_export.csv
```

Current seed behavior:

- recreates tables and stamps Alembic to `head`
- creates demo accounts and entries
- creates `admin` with password `admin`

## Run Backend + Frontend Together

```bash
./scripts/dev_up.sh
```

Behavior:

- runs `uv run alembic upgrade head`
- auto-seeds demo data only when the database is effectively empty
- runs `npm install` in `frontend/`
- starts backend and frontend
- skips Telegram polling by default; pass `./scripts/dev_up.sh --with-telegram` to opt in
- writes logs under `logs/`

## Run Backend Only

```bash
uv run bill-helper-api
```

Useful URLs:

- API: `http://localhost:8000/api/v1`
- Swagger: `http://localhost:8000/docs`
- health: `http://localhost:8000/healthz`

## Run Frontend Only

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173/login` and sign in with a password-backed account.

## Telegram

Telegram settings use `TELEGRAM_*` names, with `BILL_HELPER_TELEGRAM_*` aliases also accepted.

Important variables:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Required bot token |
| `TELEGRAM_ALLOWED_USER_IDS` | Private-chat allow-list |
| `TELEGRAM_BACKEND_BASE_URL` | Backend API base URL |
| `TELEGRAM_BACKEND_AUTH_TOKEN` | Preferred bearer token for password-mode backend auth |
| `TELEGRAM_BACKEND_AUTH_HEADERS` | Optional raw headers for custom auth or proxy/header injection |
| `TELEGRAM_WEBHOOK_SECRET` | Required only for webhook mode |

Run polling locally:

```bash
uv run python -m telegram.polling
```

Run the webhook adapter:

```bash
uv run python -m telegram.webhook
```

## Verification Gates

Run these after behavior, schema, API, tooling, or UI changes:

```bash
uv run python -m py_compile backend
OPENROUTER_API_KEY=test uv run pytest backend/tests -q -m "not workspace_docker"
# Run this as well when touching workspace lifecycle or IDE proxy behavior:
OPENROUTER_API_KEY=test uv run pytest backend/tests/test_agent_workspace.py -q -m workspace_docker
uv run python scripts/check_llm_design.py
cd frontend && npm run test && npm run test:e2e && npm run build
cd ..
uv run python scripts/check_docs_sync.py
```

When the agent workspace image changes, rebuild it locally and recreate any running sandbox containers:

```bash
docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .
for name in $(docker ps --format '{{.Names}}' | grep '^bill-helper-sandbox-'); do
  docker rm -f "$name"
done
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
- `backend/routers/agent_threads.py`
- `backend/routers/agent_runs.py`
- `backend/routers/agent_reviews.py`
- `backend/routers/agent_attachments.py`
- `backend/services/agent/runtime.py`
- `backend/services/agent/runtime_loop.py`
- `backend/services/agent/runtime_state.py`
- `backend/services/agent/run_orchestrator.py`
- `backend/services/agent/message_history.py`
- `backend/services/agent/attachment_content.py`
- `backend/services/agent/user_context.py`
- `backend/services/agent/protocol_helpers.py`
- `backend/services/agent/tool_args/`
- `backend/services/agent/proposals/`
- `backend/services/agent/read_tools/`
- `backend/services/agent/terminal.py`
- `backend/services/agent/proposal_patching.py`
- `backend/services/agent/tool_runtime.py`
- `backend/services/agent/tool_runtime_support/`
- `backend/services/agent/tools.py` (thin facade)
- `backend/services/agent/reviews/`
- `backend/services/agent/serializers.py`

Architecture quality baseline:

- follow `AGENTS.md` for anti-slop ownership boundaries and required refactor/test/doc gates

Frontend agent modules:

- render shell: `frontend/src/features/agent/AgentPanel.tsx`
- panel controller + presentation + local hooks: `frontend/src/features/agent/panel/*`
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

- `/path/to/bill_helper/skills/frontend-ui-builder/SKILL.md`

Current behavior:

- For frontend UI changes, agents should load and apply `frontend-ui-builder`.
- The skill is the default evolving repo-specific frontend build guide: it covers shared page primitives, style-layer ownership, explicit scroll/overlay design, preserving valuable bespoke interactions, tight UI copy, stricter geometry for dashboard and agent surfaces, and feeding clearly successful new conventions back into the skill.
- It is not intended for backend-only work.

Operational impact:

- No new runtime dependencies or environment variables.
- Apply the skill checklist in PRs for non-trivial UI work, especially when touching layouts, fixed-height modals, floating menus, timelines, or agent surfaces.

Affected files/modules:

- `/path/to/bill_helper/AGENTS.md`
- `/path/to/bill_helper/skills/frontend-ui-builder/SKILL.md`

Constraints:

- If existing frontend structure differs from the shared page/style ownership described in the skill, adapt while preserving the same scroll, overlay, and interaction-quality rules.

## Desloppify Skill Workflow

Skill file:

- `/path/to/bill_helper/skills/desloppify-maintenance/SKILL.md`

Current behavior:

- For explicit desloppify cleanup requests, agents should load and apply `desloppify-maintenance`.
- The skill makes `uv run desloppify ...` the default entrypoint, keeps the tool queue as the source of truth, and requires recording durable fix batches in dated fix-log docs under `docs/completed_tasks/`.
- It is not the default for ordinary feature work that does not use the desloppify workflow.

Operational impact:

- Before scanning, review generated/runtime/vendor/build directories and exclude only obvious non-source paths directly; questionable exclude candidates must be surfaced to the user first.
- Typical commands are `uv run desloppify scan --path .`, `uv run desloppify next`, the printed `uv run desloppify resolve ...` command for each completed item, and periodic `uv run desloppify plan` / `scan` refreshes when the queue shifts.
- Behavior, schema, or tooling fixes that come out of the queue must still pass the repository verification gates, including `OPENROUTER_API_KEY=test uv run pytest backend/tests -q -m "not workspace_docker"` and `uv run python scripts/check_docs_sync.py`. Also run `OPENROUTER_API_KEY=test uv run pytest backend/tests/test_agent_workspace.py -q -m workspace_docker` when the change touches workspace lifecycle or IDE proxy behavior.

Affected files/modules:

- `/path/to/bill_helper/AGENTS.md`
- `/path/to/bill_helper/skills/desloppify-maintenance/SKILL.md`
- `/path/to/bill_helper/docs/completed_tasks/2026_03_05-clean_architecture_fix_log.md`

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
- `backend/docs/*.md`, `frontend/docs/*.md`, and `docs/api/*.md` for focused subsystem reference docs.
- `tasks/*.md` for active implementation plans and temporary caveats.
- `docs/completed_tasks/*.md` for archived plans and retrospectives.

Any behavior, schema, API, tooling, or UI change must update the relevant stable docs in the canonical docs tree, `docs/features/`, or the canonical package-local subsystem docs. Use task docs for work tracking, not as the final source of truth.

Recommended before merging:

1. `OPENROUTER_API_KEY=test uv run pytest backend/tests -q -m "not workspace_docker"`
2. `OPENROUTER_API_KEY=test uv run pytest backend/tests/test_agent_workspace.py -q -m workspace_docker` when touching workspace lifecycle or IDE proxy behavior
3. `npm run build` (from `frontend/`)
4. `uv run python scripts/check_docs_sync.py`
The Playwright harness starts the backend on disposable non-default ports and copies the shared app data directory into a temporary location before applying migrations, so browser coverage stays isolated from the primary local database.
