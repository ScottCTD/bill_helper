# CALLING SPEC:
# - Purpose: provide the `config` module.
# - Inputs: callers that import `backend/config.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `config`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── XDG-conventional shared paths ────────────────────────────────────────────
# Config: ~/.config/bill-helper/.env    (secrets — shared across worktrees)
# Data:   ~/.local/share/bill_helper/   (SQLite DB, logs — shared across worktrees)
SHARED_ENV_FILE = Path.home() / ".config" / "bill-helper" / ".env"
SHARED_DATA_DIR = Path.home() / ".local" / "share" / "bill_helper"

# Layered env-file cascade (first file wins for duplicate keys):
#   1. Real environment variables        — highest priority (production / CI)
#   2. .env in CWD                       — per-worktree overrides (gitignored)
#   3. ~/.config/bill-helper/.env        — shared dev secrets across worktrees
_env_files: tuple[str, ...] = (
    ".env",
    str(SHARED_ENV_FILE),
)
DEFAULT_CORS_SCHEME = "http"
DEFAULT_CORS_HOST = "localhost"
DEFAULT_CORS_PORT = 5173
DEFAULT_AGENT_MODEL = "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"
DEFAULT_AGENT_WORKSPACE_IMAGE = "bill-helper-agent-workspace:latest"
DEFAULT_WORKSPACE_BACKEND_BASE_URL = "http://host.docker.internal:8000/api/v1"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    parsed: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        if not separator:
            continue
        normalized_key = key.strip()
        if not normalized_key:
            continue
        normalized_value = value.strip()
        if (
            len(normalized_value) >= 2
            and normalized_value[0] == normalized_value[-1]
            and normalized_value[0] in {"'", '"'}
        ):
            normalized_value = normalized_value[1:-1]
        parsed[normalized_key] = normalized_value
    return parsed


def ensure_env_file_variables_loaded() -> None:
    """Hydrate shared env-file secrets into process env for provider SDKs.

    Pydantic reads `env_file` values for declared Settings fields only. Provider
    integrations such as LiteLLM still resolve credentials directly from
    `os.environ`, so we mirror env-file variables into the process environment
    without overriding already-exported values.
    """

    for env_file in _env_files:
        env_path = Path(env_file).expanduser()
        for key, value in _parse_env_file(env_path).items():
            os.environ.setdefault(key, value)


def _default_cors_origins() -> list[str]:
    return [f"{DEFAULT_CORS_SCHEME}://{DEFAULT_CORS_HOST}:{DEFAULT_CORS_PORT}"]


class Settings(BaseSettings):
    app_name: str = "Bill Helper"
    api_prefix: str = "/api/v1"
    data_dir: Path = SHARED_DATA_DIR
    database_url: str = ""
    cors_origins: list[str] = Field(default_factory=_default_cors_origins)
    current_user_timezone: str = Field(
        default="America/Toronto",
        validation_alias=AliasChoices(
            "CURRENT_USER_TIMEZONE", "BILL_HELPER_CURRENT_USER_TIMEZONE"
        ),
    )
    default_currency_code: str = Field(
        default="CAD",
        validation_alias=AliasChoices(
            "DEFAULT_CURRENCY_CODE", "BILL_HELPER_DEFAULT_CURRENCY_CODE"
        ),
    )
    dashboard_currency_code: str = Field(
        default="CAD",
        validation_alias=AliasChoices(
            "DASHBOARD_CURRENCY_CODE", "BILL_HELPER_DASHBOARD_CURRENCY_CODE"
        ),
    )
    agent_model: str = DEFAULT_AGENT_MODEL
    agent_max_steps: int = 100
    agent_bulk_max_concurrent_threads: int = Field(default=4, ge=1, le=16)
    agent_retry_max_attempts: int = Field(default=3, ge=1, le=10)
    agent_retry_initial_wait_seconds: float = Field(default=0.25, ge=0.0, le=30.0)
    agent_retry_max_wait_seconds: float = Field(default=4.0, ge=0.0, le=120.0)
    agent_retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=10.0)
    agent_max_image_size_bytes: int = 5 * 1024 * 1024
    agent_max_images_per_message: int = 4
    agent_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AGENT_BASE_URL",
            "BILL_HELPER_AGENT_BASE_URL",
        ),
    )
    agent_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AGENT_API_KEY",
            "BILL_HELPER_AGENT_API_KEY",
        ),
    )
    agent_workspace_enabled: bool = True
    agent_workspace_image: str = DEFAULT_AGENT_WORKSPACE_IMAGE
    agent_workspace_docker_binary: str = "docker"
    workspace_backend_base_url: str = DEFAULT_WORKSPACE_BACKEND_BASE_URL

    @model_validator(mode="after")
    def _derive_database_url(self) -> Settings:
        """Derive database_url from data_dir when not explicitly provided."""
        if not self.database_url:
            self.database_url = f"sqlite:///{self.data_dir}/bill_helper.db"
        return self

    def ensure_data_dir(self) -> Path:
        """Create data_dir if it doesn't exist and return it."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    model_config = SettingsConfigDict(
        env_prefix="BILL_HELPER_",
        env_file=_env_files,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    ensure_env_file_variables_loaded()
    return Settings()
