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

- `LANGFUSE_PUBLIC_KEY` / `BILL_HELPER_LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY` / `BILL_HELPER_LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` / `BILL_HELPER_LANGFUSE_HOST`
- `AGENT_MODEL` (default `openrouter/qwen/qwen3.5-27b`)
- `AGENT_MAX_STEPS` (default `100`)
- `AGENT_MAX_IMAGE_SIZE_BYTES` (default `5MB`)
- `AGENT_MAX_IMAGES_PER_MESSAGE` (default `4`)
- `AGENT_BASE_URL` / `BILL_HELPER_AGENT_BASE_URL`
- `AGENT_API_KEY` / `BILL_HELPER_AGENT_API_KEY`

Runtime override behavior:

- `runtime_settings` stores optional per-field overrides managed by `GET/PATCH /api/v1/settings`, including `user_memory`
- effective runtime settings resolve as `override -> env default` where applicable
- `user_memory` is DB-backed only and is injected into every agent system prompt when set
- identity is request-principal-based at API boundaries; `current_user_name` is read-only in `/settings`
- `agent_base_url` overrides allow only `http` and `https` and block localhost domains and non-public IP literals

Behavior notes:

- app startup succeeds even when provider credentials are missing
- only agent execution is blocked (`503`) when LiteLLM cannot resolve credentials for the configured model target
- provider credentials are resolved from standard environment variables for the configured model
- `get_settings()` caches environment settings with `lru_cache`
- runtime behavior consumers should read through `backend/services/runtime_settings.py`
- FastAPI app construction is factory-driven via `create_app()`
- `backend.main` launches uvicorn in factory mode (`backend.main:create_app`) to avoid import-time bootstrap coupling

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
