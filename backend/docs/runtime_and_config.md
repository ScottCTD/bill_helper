# Backend Runtime And Config

## Stack

- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- Alembic
- SQLite
- LiteLLM for model-provider routing
- PyMuPDF for PDF extraction and rendering
- local `tesseract` as OCR fallback
- Docker CLI for per-user workspace provisioning

## Entry Points

- app factory + ASGI app: `backend/main.py`
- backend run command: `uv run bill-helper-api`
- health endpoint: `GET /healthz`
- admin bootstrap CLI: `uv run python scripts/bootstrap_admin.py --name <user> --password <pass>`
- Telegram polling entry point: `uv run python -m telegram.polling`
- Telegram webhook entry point: `uv run python -m telegram.webhook`

## Configuration (`backend/config.py`)

Settings use the `BILL_HELPER_` prefix.

Env files load in cascade order:

1. `.env` in the working directory
2. `~/.config/bill-helper/.env`
3. real environment variables override both

Core settings:

- `APP_NAME`
- `API_PREFIX` (default `/api/v1`)
- `DATA_DIR` (default `~/.local/share/bill_helper`)
- `DATABASE_URL` (derived from `DATA_DIR` unless explicitly set)
- `CORS_ORIGINS` (default `http://localhost:5173`)
- `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE`
- `DEFAULT_CURRENCY_CODE`
- `DASHBOARD_CURRENCY_CODE`

Agent settings:

- `AGENT_MODEL`
- `AGENT_MAX_STEPS`
- `AGENT_BULK_MAX_CONCURRENT_THREADS`
- retry policy fields
- image and attachment limit fields
- `AGENT_WORKSPACE_ENABLED`
- `AGENT_WORKSPACE_IMAGE`
- `AGENT_WORKSPACE_DOCKER_BINARY`
- `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL`
- `AGENT_API_KEY` / `BILL_HELPER_AGENT_API_KEY`

Runtime override behavior:

- `runtime_settings` stores optional per-field overrides managed by `GET/PATCH /api/v1/settings`, including ordered `user_memory` and `available_agent_models`
- effective runtime settings resolve as `override -> env default` where applicable
- `user_memory` is DB-backed only, normalized as an ordered `list[str]`, and injected into every agent system prompt as a markdown unordered list when set
- `available_agent_models` is DB-backed only, normalized as an ordered `list[str]`, and always resolved to include the effective `agent_model`
- `entry_tagging_model` is DB-backed only, may be blank, and must stay inside the effective `available_agent_models` list; blank disables inline entry tag suggestion
- identity is request-principal-based at API boundaries and is not persisted in runtime settings
- protected HTTP routes require explicit `X-Bill-Helper-Principal`; the frontend owns that header through the local principal session
- `agent_base_url` overrides allow only `http` and `https` and block localhost domains and non-public IP literals
Behavior notes:

- protected routes expect bearer tokens backed by the `sessions` table
- the web app uses the same bearer-session flow
- app startup succeeds even when provider credentials are missing
- only agent execution is blocked (`503`) when LiteLLM cannot resolve credentials for the configured model
- env-file variables are mirrored into `os.environ` so provider SDKs and LiteLLM can see shared secrets
- `get_settings()` caches environment settings with `lru_cache`

## Agent Workspace Provisioning

Relevant modules:

- `backend/services/user_files.py`
- `backend/services/agent_workspace.py`
- `backend/services/workspace_browser.py`
- `backend/services/workspace_ide.py`
- `backend/services/docker_cli.py`
- `docker/agent-workspace.dockerfile`

Current behavior:

- user creation and admin bootstrap eagerly create `{data_dir}/user_files/{user_id}/{uploads,artifacts}`
- when `agent_workspace_enabled=true`, those same flows also ensure the named Docker volume `bill-helper-workspace-{user_id}` and the named `code-server` container definition `bill-helper-sandbox-{user_id}`
- the provisioned container mounts the user's canonical file root at `/data` as read-only and a named volume at `/workspace`; the IDE-visible `user_data/` tree is no longer a separate bind mount
- the workspace image runs `code-server` as its main process, publishes its IDE port to localhost only, and uses a structured volume root where editable files live under `/workspace/workspace` and `/workspace/user_data` is a symlink to `/data/user_data/{uploads,artifacts}`, exposing friendly-name symlinks instead of raw storage UUIDs
- the workspace image preinstalls the OpenVSX web-compatible PDF viewer extension `chocolatedesue.modern-pdf-preview` and syncs it into each workspace so mounted PDFs can open inside browser-based `code-server` without manual extension setup
- the workspace entrypoint expects the current layout only: `/workspace/workspace`, `/workspace/.ide`, and `/workspace/user_data -> /data/user_data`; if `user_data` is not a symlink, startup fails instead of migrating old layouts
- `ensure_user_workspace_provisioned()` enforces the current image/label/port/mount contract and recreates mismatched containers onto the current revision without compatibility shims for older mount layouts
- `GET /api/v1/workspace` reports current container state, IDE readiness, and degraded launch reason for the authenticated user
- when the configured workspace image is missing, `GET /api/v1/workspace` returns a snapshot with `status="image_missing"` so the UI can still explain the missing image instead of returning `503`
- `POST /api/v1/workspace/start` and `POST /api/v1/workspace/stop` remain explicit lifecycle controls, but login and auth bootstrap now trigger best-effort background start attempts so the IDE is usually ready before the user opens `/workspace`
- `POST /api/v1/workspace/ide/session` mints a narrow `HttpOnly` workspace cookie for `/api/v1/workspace/ide/` and launches the same-origin IDE proxy without inventing a second auth model
- logging out only stops the workspace after the user's last active app session disappears
- the backend assumes `agent_workspace_image` already exists and returns a provisioning error if it does not
- the image can be built locally with `docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .`
- if the backend itself runs inside Docker, it still needs host-daemon access via `/var/run/docker.sock` or `DOCKER_HOST` to manage sibling user workspaces

## Session Auth Runtime

Relevant modules:

- `backend/auth/dependencies.py`
- `backend/services/passwords.py`
- `backend/services/sessions.py`
- `backend/services/principals.py`
- `backend/routers/auth.py`
- `backend/routers/admin.py`

Current behavior:

- password hashes are stored on `users.password_hash`
- bearer tokens are generated as opaque random strings
- only `SHA-256(token)` is persisted in `sessions.token_hash`
- logout or admin session deletion revokes access by deleting the row
- session expiry is nullable in the current prototype
- impersonation sessions set `is_admin_impersonation=true`

## Runtime Settings

`runtime_settings` stores optional app-wide overrides managed by `GET/PATCH /api/v1/settings`.

Supported persisted overrides include:

- `user_memory`
- `default_currency_code`
- `dashboard_currency_code`
- `agent_model`
- `entry_tagging_model`
- `available_agent_models`
- run-limit and retry fields
- attachment limits
- `agent_base_url`
- `agent_api_key`

Important constraints:

- identity is not stored in runtime settings
- `available_agent_models` is normalized to always include the effective `agent_model`
- `entry_tagging_model` must be blank or included in the effective `available_agent_models`
- `agent_base_url` only allows public `http` / `https` endpoints
- `agent_api_key` is never returned from the API

## Telegram Transport Config (`telegram/config.py`)

Telegram settings use `TELEGRAM_*` env names with `BILL_HELPER_TELEGRAM_*` aliases accepted.

Key settings:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_IDS`
- `TELEGRAM_WEBHOOK_SECRET`
- `TELEGRAM_API_BASE_URL`
- `TELEGRAM_BACKEND_BASE_URL`
- `TELEGRAM_BACKEND_AUTH_TOKEN`
- `TELEGRAM_BACKEND_AUTH_HEADERS`
- `TELEGRAM_DATA_DIR`
- `TELEGRAM_STATE_PATH`

Auth guidance:

- use `TELEGRAM_BACKEND_AUTH_TOKEN` for normal backend authentication
- use `TELEGRAM_BACKEND_AUTH_HEADERS` only when you need extra custom headers, such as proxy headers
- if `Authorization` is already present in `TELEGRAM_BACKEND_AUTH_HEADERS`, Telegram preserves it instead of synthesizing one from `TELEGRAM_BACKEND_AUTH_TOKEN`

## Database Layer (`backend/database.py`)

- `backend/db_meta.py` holds side-effect-free SQLAlchemy metadata
- `backend/database.py` exposes:
  - `build_engine_for_url(database_url)`
  - `build_engine(settings)`
  - `build_session_maker(engine)`
  - cached runtime accessors `get_engine()` and `get_session_maker()`
  - request dependency `get_db()` and helper `open_session()`, both of which now resolve the current cached sessionmaker instead of a stale import-time alias
- SQLite engines use `check_same_thread=False`
- scripts, tests, and migrations should construct dedicated engines/sessions instead of relying on runtime globals when isolation matters
