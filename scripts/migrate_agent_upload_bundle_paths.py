# CALLING SPEC:
# - Purpose: run the `migrate_agent_upload_bundle_paths` repository script.
# - Inputs: CLI flags for optional user filter, dry-run, and confirmation.
# - Outputs: printed per-row status and process exit code.
# - Side effects: optional filesystem moves and DB updates via bundle relocate helpers.
from __future__ import annotations

import argparse
import sys

from backend.config import get_settings
from backend.database import get_session_maker
from backend.services.agent.agent_upload_bundle_relocate import (
    iter_agent_attachment_bundle_primaries,
    relocate_agent_upload_bundle_primary,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate Docling bundle directories to uploads/<created-at-date>/<readable-bundle>/raw.<ext> "
            "and refresh stored_relative_path on user_files."
        )
    )
    parser.add_argument(
        "--user-id",
        default=None,
        help="Only process rows for this owner user id (default: all users).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned moves only.")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required to apply changes (ignored with --dry-run).",
    )
    parser.add_argument(
        "--timezone",
        default=None,
        help="IANA timezone for created_at → date folder (default: app current user timezone).",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.yes:
        print(
            "Refusing to migrate without --yes (or use --dry-run).",
            file=sys.stderr,
        )
        return 2

    settings = get_settings()
    settings.ensure_data_dir()
    tz = (args.timezone or settings.current_user_timezone or "UTC").strip() or "UTC"

    session = get_session_maker()()
    exit_code = 0
    try:
        rows = list(iter_agent_attachment_bundle_primaries(session, owner_user_id=args.user_id))
        print(f"candidates: {len(rows)} (timezone={tz!r})", flush=True)
        for row in rows:
            try:
                msg = relocate_agent_upload_bundle_primary(
                    session,
                    user_file=row,
                    timezone_name=tz,
                    data_dir=None,
                    dry_run=args.dry_run,
                )
                print(msg, flush=True)
                if msg.startswith("error_"):
                    exit_code = 1
            except Exception as exc:
                exit_code = 1
                print(f"error:{row.id}:{exc!r}", flush=True)
                session.rollback()
        return exit_code
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
