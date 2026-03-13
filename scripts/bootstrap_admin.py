# CALLING SPEC:
# - Purpose: run the `bootstrap_admin` repository script.
# - Inputs: callers that import `scripts/bootstrap_admin.py` and pass module-defined arguments or framework events.
# - Outputs: CLI-side workflow helpers and the `bootstrap_admin` entrypoint.
# - Side effects: command-line execution and repository automation as implemented below.
from __future__ import annotations

import argparse
import sys

from alembic import command
from alembic.config import Config

from backend.config import get_settings
from backend.database import get_session_maker
from backend.services.bootstrap import REPO_ROOT
from backend.services.users import create_or_reset_admin_user


def _build_alembic_config(*, database_url: str) -> Config:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset the primary admin user.")
    parser.add_argument("--name", required=True, help="Admin user name")
    parser.add_argument("--password", required=True, help="Admin password")
    args = parser.parse_args()

    settings = get_settings()
    settings.ensure_data_dir()

    try:
        command.upgrade(_build_alembic_config(database_url=settings.database_url), "head")

        session = get_session_maker()()
        try:
            user = create_or_reset_admin_user(
                session,
                raw_name=args.name,
                password=args.password,
            )
            session.commit()
            session.refresh(user)
            user_name = user.name
            user_id = user.id
        finally:
            session.close()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Admin user ready: {user_name} ({user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
