"""Create the default benchmark snapshot: accounts, default tags, entity categories, user memory."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = REPO_ROOT / "benchmark" / "fixtures" / "snapshots" / "default"

sys.path.insert(0, str(REPO_ROOT))


def main() -> None:
    import backend.models  # noqa: F401 — ensure all models are registered with Base
    from backend.database import Base

    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    db_path = SNAP_DIR / "db.sqlite3"
    if db_path.exists():
        db_path.unlink()

    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    make_session = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    db = make_session()

    from scripts.seed_defaults import seed_all
    result = seed_all(db, include_user_memory=True)

    print(f"Created default snapshot at {db_path}")
    print(f"  User: {result['user']}")
    print(f"  Accounts: {', '.join(result['accounts'])}")
    print(f"  Tags: {result['tags']}")
    print(f"  Entity categories: {result['entity_categories']}")
    print(f"  User memory: {'yes' if result['user_memory'] else 'no'}")

    from alembic.config import Config
    from alembic import command

    alembic_ini = REPO_ROOT / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.stamp(cfg, "head")
    print("  Alembic stamped at head")

    meta = {
        "name": "default",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "size_bytes": db_path.stat().st_size,
        "note": "Empty DB with accounts, default tags, entity categories, and user memory",
    }
    (SNAP_DIR / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")

    db.close()
    engine.dispose()


if __name__ == "__main__":
    main()
