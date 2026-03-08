# Backend Runtime And Config

## Stack

- FastAPI
- SQLAlchemy 2.x
- Pydantic v2
- Alembic
- SQLite (local file)
- LiteLLM model-provider routing for chat completions
- PyMuPDF (`pymupdf`) for PDF text extraction and page rendering in agent message history
- local Tesseract CLI (`tesseract`) as OCR fallback for PDFs whose native text extraction returns no usable text

## Entry Points

- App factory + ASGI app: `backend/main.py`
- Backend run command: `uv run bill-helper-api`
- Health endpoint: `GET /healthz`
- Telegram polling entry point: `uv run python -m telegram.polling`
- Telegram webhook entry point: `uv run python -m telegram.webhook`

## Configuration (`backend/config.py`)

Settings use the `BILL_HELPER_` prefix.

Env files are loaded in cascade order:

1. `.env` in the working directory for per-worktree overrides
2. `~/.config/bill-helper/.env` for shared dev secrets across worktrees

Real environment variables always take highest priority. See `docs/development.md` for setup details.

Core app settings include:

- `APP_NAME`
- `API_PREFIX` (default `/api/v1`)
- `DATA_DIR` (default `~/.local/share/bill-helper`)
- `DATABASE_URL` (derived from `DATA_DIR` unless explicitly set)
- `CORS_ORIGINS` (default `http://localhost:5173`)
- `CURRENT_USER_NAME` (default `admin`)
- `CURRENT_USER_TIMEZONE` / `BILL_HELPER_CURRENT_USER_TIMEZONE` (default `America/Toronto`)
- `DEFAULT_CURRENCY_CODE` (default `CAD`)
- `DASHBOARD_CURRENCY_CODE` (default `CAD`)

Agent settings include:

- `AGENT_MODEL` (default `bedrock/us.anthropic.claude-sonnet-4-6`)
- `AGENT_MAX_STEPS` (default `100`)
- `AGENT_BULK_MAX_CONCURRENT_THREADS` (default `4`)
- `AGENT_MAX_IMAGE_SIZE_BYTES` (default `5MB`)
- `AGENT_MAX_IMAGES_PER_MESSAGE` (default `4`)
- `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL`
- `AGENT_API_KEY` / `BILL_HELPER_AGENT_API_KEY`

Runtime override behavior:

- `runtime_settings` stores optional per-field overrides managed by `GET/PATCH /api/v1/settings`, including ordered `user_memory` and `available_agent_models`
- effective runtime settings resolve as `override -> env default` where applicable
- `user_memory` is DB-backed only, normalized as an ordered `list[str]`, and injected into every agent system prompt as a markdown unordered list when set
- `available_agent_models` is DB-backed only, normalized as an ordered `list[str]`, and always resolved to include the effective `agent_model`
- identity is request-principal-based at API boundaries; `current_user_name` is read-only in `/settings`
- `agent_base_url` overrides allow only `http` and `https` and block localhost domains and non-public IP literals

Behavior notes:

- app startup succeeds even when provider credentials are missing
- only agent execution is blocked (`503`) when LiteLLM cannot resolve credentials for the configured model target
- provider credentials are resolved by LiteLLM from standard provider-specific environment variables for the configured model
- provider-specific secrets from `.env` or `~/.config/bill-helper/.env` are mirrored into `os.environ` before LiteLLM validation and model calls, so shared XDG env files work for direct provider lookups such as `AWS_BEARER_TOKEN_BEDROCK`
- `agent_base_url` and `agent_api_key` are explicit app-level overrides only; provider-native env vars are not forwarded through those fields
- `get_settings()` caches environment settings with `lru_cache`
- runtime behavior consumers should read through `backend/services/runtime_settings.py`
- FastAPI app construction is factory-driven via `create_app()`
- `backend.main` launches uvicorn in factory mode (`backend.main:create_app`) to avoid import-time bootstrap coupling

## Telegram Transport Config (`telegram/config.py`)

- Telegram settings use `TELEGRAM_*` env names with `BILL_HELPER_TELEGRAM_*` aliases also accepted.
- The Telegram adapter reads the same env cascade as the backend: working-tree `.env`, then `~/.config/bill-helper/.env`, then real environment variables.
- Key settings: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USER_IDS`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_API_BASE_URL`, `TELEGRAM_BACKEND_BASE_URL`, `TELEGRAM_BACKEND_AUTH_TOKEN`, `TELEGRAM_BACKEND_AUTH_HEADERS`, `TELEGRAM_DATA_DIR`, and `TELEGRAM_STATE_PATH`.
- Default Telegram data dir is `{SHARED_DATA_DIR}/telegram`; default state path is `{data_dir}/chat_state.json`.
- `TELEGRAM_ALLOWED_USER_IDS` accepts either a comma-separated list or JSON array of positive Telegram user IDs. The default is empty, which denies all private-chat Telegram commands and content messages until an allow-list is configured.
- `TELEGRAM_BACKEND_AUTH_HEADERS` must decode to a JSON object; if it already provides `Authorization`, that header is preserved instead of synthesizing a bearer token from `TELEGRAM_BACKEND_AUTH_TOKEN`.
- `telegram.config.get_settings()` is cached with `lru_cache`, mirroring the backend settings access pattern.

## Database Layer (`backend/database.py`)

- side-effect-free metadata lives in `backend/db_meta.py` (`Base`)
- `backend/database.py` exposes explicit factories:
  - `build_engine_for_url(database_url)`
  - `build_engine(settings)`
  - `build_session_maker(engine)`
  - cached runtime accessors `get_engine()` and `get_session_maker()`
  - request dependency `get_db()` and helper `open_session()`
- SQLite engines keep `check_same_thread=False`
- scripts, migrations, and tests that need dedicated DB handles should construct their own engine and session explicitly instead of importing runtime globals
