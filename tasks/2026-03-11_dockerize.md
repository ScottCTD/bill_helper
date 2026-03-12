# Dockerize: Backend + Frontend + Telegram

## Goal

Create a Docker setup so the entire app can run with `docker compose up`.
Keep it simple for now (pre-alpha prototype). Design for future extensibility
(sandbox containers per the agent-workspace plan in `tasks/2026-03-03_agent_workspace.md`).

## Architecture

```
docker-compose.yml
├── backend   (FastAPI serves API + static frontend build, port 8000)
└── telegram  (same image, different entrypoint, optional via Compose profile)
```

Single multi-stage `Dockerfile` produces one image used by both services.
Frontend is built in a Node stage, then the `dist/` output is copied into the
backend image and served via FastAPI `StaticFiles`.

SQLite stays as the database — the DB file lives on a named Docker volume.

### Future extensibility

- Postgres can be added as a Compose service later (one-line `DATABASE_URL` change).
- Sandbox containers (agent workspace) will be added to the same Compose file.
- Frontend can be moved to an nginx/Caddy service when production perf matters.

## Files to Create

### 1. `Dockerfile` (multi-stage)

```dockerfile
# ── Stage 1: build frontend ──────────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# Output: /build/dist/

# ── Stage 2: app (backend + telegram) ────────────────────────────────────
FROM python:3.13-slim AS app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install Python dependencies (cache-friendly layer ordering)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code
COPY backend/ backend/
COPY telegram/ telegram/
COPY alembic/ alembic/
COPY alembic.ini ./
COPY scripts/seed_defaults.py scripts/seed_defaults.py
COPY conftest.py ./

# Copy built frontend
COPY --from=frontend-build /build/dist/ /app/frontend/dist/

# Copy entrypoint
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

# Install the project itself (editable-style so `backend` and `telegram` are importable)
RUN uv sync --frozen --no-dev

ENV BILL_HELPER_DATA_DIR=/data
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["backend"]
```

### 2. `docker-entrypoint.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Ensure data directory exists
mkdir -p "${BILL_HELPER_DATA_DIR:-/data}"

case "${1:-backend}" in
  backend)
    echo "Running database migrations..."
    uv run alembic upgrade head
    echo "Starting backend..."
    exec uv run uvicorn backend.main:create_app \
      --host 0.0.0.0 --port 8000 --factory
    ;;
  telegram)
    echo "Starting Telegram bot..."
    exec uv run python -m telegram.polling
    ;;
  *)
    exec "$@"
    ;;
esac
```

### 3. `docker-compose.yml`

```yaml
services:
  backend:
    build: .
    command: ["backend"]
    ports:
      - "${BILL_HELPER_PORT:-8000}:8000"
    volumes:
      - bill-helper-data:/data
    env_file:
      - path: .env
        required: false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 15s

  telegram:
    build: .
    command: ["telegram"]
    volumes:
      - bill-helper-data:/data
    env_file:
      - path: .env
        required: false
    environment:
      TELEGRAM_BACKEND_BASE_URL: http://backend:8000/api/v1
    depends_on:
      backend:
        condition: service_healthy
    profiles:
      - telegram

volumes:
  bill-helper-data:
```

Usage:
- `docker compose up` — backend only
- `docker compose --profile telegram up` — backend + telegram

### 4. `.dockerignore`

```
.git
.env
__pycache__
*.pyc
*.pyo
node_modules
frontend/dist
logs/
output/
notebooks/
ios/
skills/
benchmark/
dist/
.vite
*.egg-info
.pytest_cache
```

### 5. Backend code change: serve static frontend

In `backend/main.py`, after all routers are mounted, add a `StaticFiles` mount
for the frontend build. This must be the **last** mount so it doesn't shadow
API routes. Also add an SPA fallback so client-side routes (e.g. `/entries`)
serve `index.html`.

```python
# At the end of create_app(), before `return app`:
import os
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.is_dir():
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        """Serve index.html for any non-API, non-static path (SPA routing)."""
        file_path = frontend_dist / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")
```

**Important**: The SPA fallback must not match `/api/*` or `/healthz` or `/docs`
or `/openapi.json`. Since FastAPI matches routes in registration order and the
API routers are registered first, this works — the catch-all only fires for
paths that don't match any API route.

### 6. Config adjustment for Docker

The `BILL_HELPER_DATA_DIR` env var already controls where the SQLite DB lives.
Inside Docker this is set to `/data` (a mounted volume). The existing
`Settings._derive_database_url` will produce `sqlite:////data/bill_helper.db`.
No code change needed — the env var is sufficient.

The `TELEGRAM_BACKEND_BASE_URL` default is `http://localhost:8000/api/v1`.
Inside Docker Compose, the telegram service reaches the backend via the
Compose service name — already set in the compose definition above as
`TELEGRAM_BACKEND_BASE_URL: http://backend:8000/api/v1`.

### 7. `.env.example` update

Add a Docker section to the existing `.env.example`:

```bash
# ── Docker ───────────────────────────────────────────────────────────────
# BILL_HELPER_PORT=8000          # host port for the web UI + API
# BILL_HELPER_DATA_DIR=/data     # inside container; don't change unless you know why
```

## Implementation Checklist

- [ ] Create `Dockerfile` (multi-stage: frontend build → app)
- [ ] Create `docker-entrypoint.sh`
- [ ] Create `docker-compose.yml`
- [ ] Create `.dockerignore`
- [ ] Add static frontend serving + SPA fallback to `backend/main.py`
- [ ] Add Docker section to `.env.example`
- [ ] Add `curl` to the Docker image (needed for healthcheck)
- [ ] Test: `docker compose build`
- [ ] Test: `docker compose up` — verify frontend loads at `http://localhost:8000`
- [ ] Test: `docker compose --profile telegram up` — verify telegram starts
- [ ] Test: API calls work through the same port (`/api/v1/...`)
- [ ] Update `README.md` with Docker quickstart section
- [ ] Update `docs/repository-structure.md` with new files
- [ ] Run `uv run python scripts/check_docs_sync.py`

## Design Decisions

1. **Single image, two entrypoints** — keeps the build simple, one image to push.
2. **FastAPI serves static files** — avoids nginx complexity for now. Swap to
   nginx later by adding a Compose service and removing the `StaticFiles` mount.
3. **SQLite on a named volume** — data persists across container restarts.
   Swap to Postgres later by adding a `postgres` service and changing
   `BILL_HELPER_DATABASE_URL`.
4. **Telegram via Compose profile** — doesn't start unless explicitly requested,
   matching the current `dev_up.py` behavior of skipping when unconfigured.
5. **Entrypoint runs migrations** — `alembic upgrade head` runs before the
   backend starts. Safe because it's idempotent.
6. **`env_file` with `required: false`** — Compose won't fail if `.env` doesn't
   exist; defaults from `Settings` classes apply.
