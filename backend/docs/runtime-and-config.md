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
- `DATA_DIR` (default `~/.local/share/bill-helper`)
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
- `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL`
- `AGENT_API_KEY` / `BILL_HELPER_AGENT_API_KEY`

Behavior notes:

- protected routes expect bearer tokens backed by the `sessions` table
- the web app uses the same bearer-session flow
- app startup succeeds even when provider credentials are missing
- only agent execution is blocked (`503`) when LiteLLM cannot resolve credentials for the configured model
- env-file variables are mirrored into `os.environ` so provider SDKs and LiteLLM can see shared secrets
- `get_settings()` caches environment settings with `lru_cache`

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
- `available_agent_models`
- run-limit and retry fields
- attachment limits
- `agent_base_url`
- `agent_api_key`

Important constraints:

- identity is not stored in runtime settings
- `available_agent_models` is normalized to always include the effective `agent_model`
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
  - request dependency `get_db()` and helper `open_session()`
- SQLite engines use `check_same_thread=False`
- scripts, tests, and migrations should construct dedicated engines/sessions instead of relying on runtime globals when isolation matters
