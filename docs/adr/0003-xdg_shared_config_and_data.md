# ADR 0003: XDG-Based Shared Configuration and Data Directories

- Status: accepted
- Date: 2026-03-04
- Deciders: scottcui

Update 2026-03-22: ADR 0007 supersedes the original agent-file sublayout. Shared data still lives under `~/.local/share/bill_helper/`, but durable user-visible files now live under `user_files/{user_id}/uploads` instead of `agent_uploads/`.

## Context

Bill Helper stores configuration (`.env`) and data (`.data/bill_helper.db`, agent uploads) in the repository working tree. Both paths are gitignored.

This creates two problems:

1. **Git worktrees don't share secrets.** Each worktree has its own working tree, so `.env` files with provider API keys don't carry over. New worktrees start without required credentials.

2. **Git worktrees don't share data.** The SQLite database at `./.data/bill_helper.db` is per-worktree. Every new worktree requires a full migration cycle and re-seeding, even when the developer wants to work against the same dataset.

Both issues made the worktree-based workflow (common for parallel feature development) impractical.

## Decision

Adopt [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/latest/) conventions to store user-level configuration and data in well-known home-directory locations, shared across all worktrees by default.

### Directory Layout

| Purpose | Path | XDG variable |
|---------|------|-------------|
| Configuration (secrets) | `~/.config/bill-helper/.env` | `XDG_CONFIG_HOME` |
| Application data (DB, uploads) | `~/.local/share/bill_helper/` | `XDG_DATA_HOME` |

### Configuration Cascade

Pydantic-settings v2 supports `env_file` as a tuple. The **first file wins** for duplicate keys:

```
Priority 1:  Real environment variables     (production / CI — platform-injected)
Priority 2:  .env in CWD                    (per-worktree overrides — gitignored)
Priority 3:  ~/.config/bill-helper/.env     (shared dev secrets — all worktrees)
Priority 4:  Defaults in backend/config.py  (sensible fallbacks)
```

Implementation in `backend/config.py`:

```python
SHARED_ENV_FILE = Path.home() / ".config" / "bill-helper" / ".env"

_env_files = (".env", str(SHARED_ENV_FILE))

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files, ...)
```

### Data Directory Cascade

A new `data_dir` setting controls where application data lives. `database_url` is derived from it when not explicitly set:

```
Priority 1:  BILL_HELPER_DATABASE_URL       (explicit DB URL — e.g., PostgreSQL in prod)
Priority 2:  BILL_HELPER_DATA_DIR           (custom data dir → DB path derived)
Priority 3:  Default                         (~/.local/share/bill_helper/)
```

Implementation in `backend/config.py`:

```python
SHARED_DATA_DIR = Path.home() / ".local" / "share" / "bill_helper"

class Settings(BaseSettings):
    data_dir: Path = SHARED_DATA_DIR
    database_url: str = ""

    @model_validator(mode="after")
    def _derive_database_url(self) -> Settings:
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir}/bill_helper.db"
        return self
```

### Data Directory Contents

```
~/.local/share/bill_helper/
├── bill_helper.db                # SQLite database
└── user_files/                   # Canonical per-user durable files
    └── {user_id}/
        ├── uploads/
```

### Environment-Specific Behavior

| Environment | Config source | Data source | Notes |
|-------------|--------------|-------------|-------|
| **Dev (default)** | `~/.config/bill-helper/.env` | `~/.local/share/bill_helper/` | Shared across all worktrees |
| **Dev (isolated)** | `.env` in CWD | Set `BILL_HELPER_DATA_DIR=./.data` in local `.env` | Per-worktree isolation |
| **Production** | Platform env vars | `BILL_HELPER_DATABASE_URL` points to managed DB | No `.env` files |
| **CI / Tests** | `BILL_HELPER_DATABASE_URL` override | Per-run temp DB | Tests use `.data/test_bill_helper.db` |

### Affected Modules

All code that previously used hardcoded `.data/` paths was updated to read from `Settings`:

| Module | Before | After |
|--------|--------|-------|
| `backend/config.py` | `database_url = "sqlite:///./.data/..."` | `data_dir` + `model_validator` derivation |
| `backend/main.py` | `Path(".data").mkdir(...)` | `settings.ensure_data_dir()` |
| `backend/services/user_files.py` | `Path(".data") / "agent_uploads"` | `get_settings().data_dir / "user_files"` |
| `benchmark/snapshot.py` | `REPO_ROOT / ".data" / "bill_helper.db"` | `get_settings().data_dir / "bill_helper.db"` |
| `scripts/seed_defaults.py` | `REPO_ROOT / ".data" / "bill_helper.db"` | `get_settings().data_dir / "bill_helper.db"` |
| `alembic/env.py` | _(no change — already reads from Settings)_ | Same |
| `backend/tests/conftest.py` | _(no change — intentionally per-worktree)_ | Same |

## Consequences

### Positive

- **Worktree-friendly:** New worktrees immediately have access to secrets and data with zero setup.
- **Single source of truth:** Secrets and data live in one place. No need to copy `.env` files between directories.
- **Production-clean:** In production, all config comes from platform env vars. No `.env` files needed, no filesystem path assumptions.
- **Fully overridable:** Every layer can be overridden. `BILL_HELPER_DATA_DIR=./.data` in a local `.env` restores the old per-worktree behavior.
- **XDG-standard:** Follows the same convention used by `git`, `docker`, `npm`, and most CLI tools on macOS/Linux.
- **Zero new dependencies:** Uses pydantic-settings' native `env_file` tuple support and stdlib `pathlib`.

### Negative

- **Migration required:** Existing data in `.data/` must be moved to `~/.local/share/bill_helper/`. A helper script (`scripts/setup_shared_env.sh`) and manual migration handle this.
- **Shared mutable state:** Two worktrees running simultaneously against the same SQLite DB may hit locking. SQLite WAL mode mitigates this for read-heavy workloads, but concurrent writes from two servers are not supported. For parallel dev servers, use `BILL_HELPER_DATA_DIR=./.data` to isolate.
- **Home directory dependency:** The default paths assume `~` is writable and stable. Docker/CI environments may need explicit overrides via `BILL_HELPER_DATA_DIR`.

### Risks

- **Concurrent SQLite access:** Mitigated by WAL mode (already enabled by SQLAlchemy defaults) and the expectation that developers run one dev server at a time. Documented as a known limitation.
- **Stale data after branch switch:** If two worktrees run different migration versions, the shared DB may become inconsistent. Mitigated by always running `alembic upgrade head` on startup (handled by `dev_up.sh`).
