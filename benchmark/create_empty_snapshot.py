"""Create the default benchmark snapshot: accounts, default tags, entity categories, user memory."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from backend.database import build_engine_for_url, build_session_maker
import backend.models_agent  # noqa: F401
import backend.models_finance  # noqa: F401
from backend.db_meta import Base
from backend.services.bootstrap import (
    run_schema_seed_and_stamp,
    stamp_alembic_head_for_sqlite_path,
)
from benchmark.io_utils import atomic_write_json
from benchmark.paths import SNAPSHOTS_DIR
from scripts.seed_defaults import seed_all
from sqlalchemy.orm import Session

SNAP_DIR = SNAPSHOTS_DIR / "default"


@dataclass(slots=True)
class SnapshotCreationResult:
    db_path: Path
    user_name: str
    account_names: list[str]
    tag_count: int
    entity_category_count: int
    has_user_memory: bool


def _seed_default_snapshot(db: Session, *, db_path: Path) -> SnapshotCreationResult:
    result = seed_all(db, include_user_memory=True)
    meta = {
        "name": "default",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "size_bytes": db_path.stat().st_size,
        "note": "Empty DB with accounts, default tags, entity categories, and user memory",
    }
    atomic_write_json(SNAP_DIR / "metadata.json", meta)
    return SnapshotCreationResult(
        db_path=db_path,
        user_name=str(result["user"]),
        account_names=[str(name) for name in result["accounts"]],
        tag_count=int(result["tags"]),
        entity_category_count=int(result["entity_categories"]),
        has_user_memory=bool(result["user_memory"]),
    )


def create_default_snapshot() -> SnapshotCreationResult:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    db_path = SNAP_DIR / "db.sqlite3"
    if db_path.exists():
        db_path.unlink()

    engine = build_engine_for_url(f"sqlite:///{db_path}")
    make_session = build_session_maker(engine)
    return run_schema_seed_and_stamp(
        engine=engine,
        metadata=Base.metadata,
        make_session=make_session,
        seed=lambda db: _seed_default_snapshot(db, db_path=db_path),
        recreate_schema=False,
        stamp=lambda: stamp_alembic_head_for_sqlite_path(db_path),
    )


def main() -> int:
    try:
        result = create_default_snapshot()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Created default snapshot at {result.db_path}")
    print(f"  User: {result.user_name}")
    print(f"  Accounts: {', '.join(result.account_names)}")
    print(f"  Tags: {result.tag_count}")
    print(f"  Entity categories: {result.entity_category_count}")
    print(f"  User memory: {'yes' if result.has_user_memory else 'no'}")
    print("  Alembic stamped at head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
