# Completed Plan: XDG-Based Shared Configuration and Data Directories

## Goal

Enable Git worktree workflows by sharing configuration (secrets) and application data (SQLite DB, uploads) across all worktrees, while preserving per-worktree override capability and Docker/production readiness.

## Problem

Bill Helper stored configuration (`.env`) and data (`.data/bill_helper.db`, agent uploads) inside the repository working tree. Both paths are gitignored. Git worktrees have isolated working trees, so:

1. **Secrets didn't carry over.** New worktrees started without `OPENROUTER_API_KEY`, Langfuse credentials, etc. The app behaved as if credentials were missing.
2. **Data didn't carry over.** Each worktree got its own empty SQLite database, requiring a full migration + seed cycle even when the developer wanted the same dataset.

## Design

### Core Principle: Layered Cascade with XDG Conventions

Adopt [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/) conventions for user-level shared paths:

| Purpose | Shared path | XDG variable |
|---------|-------------|-------------|
| Secrets / config | `~/.config/bill-helper/.env` | `XDG_CONFIG_HOME` |
| Application data | `~/.local/share/bill-helper/` | `XDG_DATA_HOME` |

### Configuration Cascade

Pydantic-settings v2 natively supports `env_file` as a tuple. First file wins for duplicate keys:

| Priority | Source | Purpose |
|----------|--------|---------|
| 1 (highest) | Real environment variables | Production / CI (platform-injected) |
| 2 | `.env` in working directory | Per-worktree overrides (gitignored) |
| 3 | `~/.config/bill-helper/.env` | Shared dev secrets across all worktrees |
| 4 (lowest) | Defaults in `backend/config.py` | Sensible fallbacks |

### Data Directory Cascade

A `data_dir` setting controls where application data lives. `database_url` is automatically derived from it via a Pydantic `model_validator` when not explicitly set:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | `BILL_HELPER_DATABASE_URL` | Explicit DB URL (e.g., `postgresql://...`) |
| 2 | `BILL_HELPER_DATA_DIR` | Custom data dir → DB path derived |
| 3 | Default | `~/.local/share/bill-helper/bill_helper.db` |

### Data Directory Contents

```
~/.local/share/bill-helper/
├── bill_helper.db          # SQLite database
└── agent_uploads/          # File attachments from agent conversations
    └── {message_id}/
        └── {filename}
```

### Environment-Specific Behavior

| Environment | Config source | Data source | Notes |
|-------------|--------------|-------------|-------|
| **Dev (default)** | `~/.config/bill-helper/.env` | `~/.local/share/bill-helper/` | Shared across all worktrees automatically |
| **Dev (isolated)** | `.env` in CWD | `BILL_HELPER_DATA_DIR=./.data` | Per-worktree isolation for migration testing |
| **Docker (SQLite)** | `docker run -e` / compose `environment:` | `BILL_HELPER_DATA_DIR=/data` + volume mount | No `.env` files needed |
| **Docker (PostgreSQL)** | `docker run -e` / compose `environment:` | `BILL_HELPER_DATABASE_URL=postgresql://...` | `data_dir` still used for agent uploads |
| **CI / Tests** | `BILL_HELPER_DATABASE_URL` env override | Per-run temp DB in `.data/` | Intentionally per-worktree |

### Docker Readiness

The cascade is designed so Docker never touches the XDG defaults:

```yaml
# docker-compose.yml — SQLite
services:
  app:
    build: .
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - BILL_HELPER_DATA_DIR=/data
    volumes:
      - app-data:/data
volumes:
  app-data:
```

```yaml
# docker-compose.yml — PostgreSQL
services:
  app:
    build: .
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
      - BILL_HELPER_DATABASE_URL=postgresql://user:pass@db:5432/bill_helper
      - BILL_HELPER_DATA_DIR=/data          # agent uploads
    volumes:
      - app-uploads:/data/agent_uploads
  db:
    image: postgres:16
    volumes:
      - pg-data:/var/lib/postgresql/data
volumes:
  app-uploads:
  pg-data:
```

The three override points that make this future-proof:

1. **`BILL_HELPER_DATABASE_URL`** — when set, completely bypasses `data_dir` for DB. This is the PostgreSQL escape hatch.
2. **`BILL_HELPER_DATA_DIR`** — controls where SQLite + uploads live. In Docker: point at a volume mount.
3. **Real env vars** — always highest priority, so Docker `-e` flags and compose `environment:` blocks just work.

### Why Zero New Dependencies

- Pydantic-settings v2 already supports `env_file` as a tuple — no new library needed.
- `model_validator` is built into Pydantic v2 — derives `database_url` from `data_dir`.
- `pathlib.Path.home()` is stdlib — resolves XDG paths at import time.
- `~/.config/` and `~/.local/share/` are standard on macOS and Linux.

## Implementation

### Key Implementation: `backend/config.py`

```python
SHARED_ENV_FILE = Path.home() / ".config" / "bill-helper" / ".env"
SHARED_DATA_DIR = Path.home() / ".local" / "share" / "bill-helper"

_env_files = (".env", str(SHARED_ENV_FILE))

class Settings(BaseSettings):
    data_dir: Path = SHARED_DATA_DIR
    database_url: str = ""

    @model_validator(mode="after")
    def _derive_database_url(self) -> Settings:
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir}/bill_helper.db"
        return self

    def ensure_data_dir(self) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    model_config = SettingsConfigDict(
        env_prefix="BILL_HELPER_",
        env_file=_env_files,
        ...
    )
```

### Files Changed

| File | Change |
|------|--------|
| `backend/config.py` | Added `SHARED_ENV_FILE`, `SHARED_DATA_DIR`, `data_dir` field, `model_validator`, `ensure_data_dir()` |
| `backend/main.py` | Uses `settings.ensure_data_dir()` instead of hardcoded `Path(".data")` |
| `backend/routers/agent.py` | Uses `get_settings().data_dir / "agent_uploads"` (2 instances) |
| `benchmark/snapshot.py` | Uses `get_settings().data_dir` for production DB path via `_production_db_path()` |
| `scripts/seed_defaults.py` | `reset_local_db()` and `seed_user_memory()` use `get_settings().data_dir` |
| `alembic.ini` | Updated placeholder comment (runtime always reads from Settings via `alembic/env.py`) |
| `alembic/env.py` | No change needed — already reads from `settings.database_url` |
| `backend/tests/conftest.py` | No change — intentionally uses per-worktree `.data/test_bill_helper.db` |
| `.env.example` | New file — documents all env vars (committed, no secrets) |
| `scripts/setup_shared_env.sh` | New file — copies `.env` to shared location or creates template |

### Documentation Updated

| Doc | Change |
|-----|--------|
| `README.md` | Quick Start → shared env setup instructions |
| `docs/development.md` | Env cascade + shared data directory sections, env var table |
| `docs/backend.md` | Config section updated with cascade + `data_dir` |
| `docs/architecture.md` | DB and upload paths use `{data_dir}` |
| `docs/api.md` | Upload path references updated |
| `docs/data-model.md` | Upload path references updated |
| `docs/high-level-data-flow.md` | Mermaid diagram updated |
| `docs/agent-billing-assistant.md` | Upload cleanup path updated |
| `docs/repository-structure.md` | Added `.env.example`, `setup_shared_env.sh`, updated `.data` note |
| `docs/README.md` | Added ADR index entry |
| `docs/adr/0003-xdg-shared-config-and-data.md` | Full architecture decision record |

## Worktree Quick Reference

```bash
# One-time setup (copies your .env to shared location)
./scripts/setup_shared_env.sh

# New worktree — secrets and data are already available
git worktree add ../bill_helper-feature feature-branch
cd ../bill_helper-feature
uv sync --extra dev
./scripts/dev_up.sh    # migrations run against shared DB automatically

# Per-worktree isolation (when needed)
echo "BILL_HELPER_DATA_DIR=./.data" > .env
```

## Known Limitations

- **Concurrent SQLite writes:** Two dev servers against the same shared DB may hit locking. Use `BILL_HELPER_DATA_DIR=./.data` to isolate when running parallel servers.
- **Migration version skew:** If worktrees are on different migration versions, the shared DB may need `alembic upgrade head` when switching. `dev_up.sh` handles this automatically.
- **Home directory assumption:** Defaults assume `~` is writable. Docker/CI environments should always set `BILL_HELPER_DATA_DIR` explicitly.

## Future Extensions

- **S3/object storage for uploads:** Add an `UPLOAD_BACKEND` setting alongside `data_dir`. Additive change, not structural.
- **PostgreSQL in production:** Already supported via `BILL_HELPER_DATABASE_URL`. No changes needed.
- **Docker deployment:** Structure is ready (see Docker Readiness section above).
