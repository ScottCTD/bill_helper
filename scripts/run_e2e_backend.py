from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADMIN_NAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin-password"
DEFAULT_SHARED_DATA_DIR = Path.home() / ".local" / "share" / "bill-helper"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the backend against a disposable database for Playwright e2e tests.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host for uvicorn.")
    parser.add_argument("--port", type=int, default=8010, help="Bind port for uvicorn.")
    parser.add_argument(
        "--frontend-origin",
        required=True,
        help="Allowed frontend origin used by the Playwright dev server.",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Optional override for the disposable backend data dir.",
    )
    parser.add_argument(
        "--source-data-dir",
        type=Path,
        default=None,
        help="Optional source data dir to copy into the disposable e2e workspace before migrations run.",
    )
    parser.add_argument(
        "--admin-name",
        default=DEFAULT_ADMIN_NAME,
        help="Admin username to seed into the disposable database.",
    )
    parser.add_argument(
        "--admin-password",
        default=DEFAULT_ADMIN_PASSWORD,
        help="Admin password to seed into the disposable database.",
    )
    parser.add_argument(
        "--log-level",
        default="warning",
        help="uvicorn log level for the disposable backend.",
    )
    return parser


def _default_data_dir(*, port: int) -> Path:
    temp_root = Path(tempfile.gettempdir()) / "bill-helper-playwright-e2e"
    return temp_root / f"backend-{port}"


def _default_source_data_dir() -> Path:
    return Path(
        os.environ.get("BILL_HELPER_E2E_SOURCE_DATA_DIR", str(DEFAULT_SHARED_DATA_DIR))
    ).expanduser()


def _prepare_isolated_data_dir(*, source_data_dir: Path, target_data_dir: Path) -> None:
    shutil.rmtree(target_data_dir, ignore_errors=True)
    if source_data_dir.exists():
        shutil.copytree(source_data_dir, target_data_dir)
    else:
        target_data_dir.mkdir(parents=True, exist_ok=True)


def _configure_environment(*, data_dir: Path, frontend_origin: str) -> None:
    os.environ["BILL_HELPER_DATA_DIR"] = str(data_dir)
    os.environ.pop("BILL_HELPER_DATABASE_URL", None)
    os.environ["BILL_HELPER_CORS_ORIGINS"] = json.dumps([frontend_origin])


def _build_alembic_config(*, database_url: str):
    from alembic.config import Config

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def _prepare_database(*, admin_name: str, admin_password: str) -> None:
    from alembic import command

    from backend.config import get_settings
    from backend.database import get_session_maker
    from backend.services.users import create_or_reset_admin_user

    settings = get_settings()
    settings.ensure_data_dir()
    command.upgrade(_build_alembic_config(database_url=settings.database_url), "head")

    session = get_session_maker()()
    try:
        create_or_reset_admin_user(
            session,
            raw_name=admin_name,
            password=admin_password,
        )
        session.commit()
    finally:
        session.close()


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    data_dir = (args.data_dir or _default_data_dir(port=args.port)).resolve()
    source_data_dir = (args.source_data_dir or _default_source_data_dir()).resolve()
    _prepare_isolated_data_dir(source_data_dir=source_data_dir, target_data_dir=data_dir)
    _configure_environment(data_dir=data_dir, frontend_origin=args.frontend_origin)

    try:
        _prepare_database(
            admin_name=args.admin_name,
            admin_password=args.admin_password,
        )

        import uvicorn

        uvicorn.run(
            "backend.main:create_app",
            host=args.host,
            port=args.port,
            factory=True,
            log_level=args.log_level,
        )
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        print(f"Disposable e2e backend failed: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
