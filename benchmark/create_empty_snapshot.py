"""Create a minimal snapshot DB with only accounts, their entities, and a user."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.database import Base
from backend.models import Account, Entity, RuntimeSettings, User

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = REPO_ROOT / "benchmark" / "fixtures" / "snapshots" / "default"


def _read_production_user_memory() -> str | None:
    """Read user_memory from the production DB's runtime_settings."""
    prod_db = REPO_ROOT / ".data" / "bill_helper.db"
    if not prod_db.exists():
        return None
    prod_engine = create_engine(
        f"sqlite:///{prod_db}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    prod_session = sessionmaker(bind=prod_engine, class_=Session)()
    try:
        from sqlalchemy import select
        row = prod_session.scalar(
            select(RuntimeSettings).where(RuntimeSettings.scope == "default")
        )
        return row.user_memory if row else None
    except Exception:
        return None
    finally:
        prod_session.close()
        prod_engine.dispose()


def main() -> None:
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

    user = User(name="admin")
    db.add(user)
    db.flush()

    debit_entity = Entity(name="Scotiabank Debit", category="account")
    credit_entity = Entity(name="Scotiabank Credit", category="account")
    db.add_all([debit_entity, credit_entity])
    db.flush()

    debit_account = Account(
        owner_user_id=user.id,
        entity_id=debit_entity.id,
        name="Scotiabank Debit",
        currency_code="CAD",
        is_active=True,
    )
    credit_account = Account(
        owner_user_id=user.id,
        entity_id=credit_entity.id,
        name="Scotiabank Credit",
        currency_code="CAD",
        is_active=True,
    )
    db.add_all([debit_account, credit_account])
    db.flush()

    user_memory = _read_production_user_memory()
    if user_memory:
        settings_row = RuntimeSettings(scope="default", user_memory=user_memory)
        db.add(settings_row)
        print(f"  User memory: {user_memory[:80]}...")
    else:
        print("  User memory: (none found in production DB)")

    db.commit()

    print(f"Created empty snapshot at {db_path}")
    print(f"  User: {user.name}")
    print(f"  Accounts: {debit_account.name}, {credit_account.name}")
    print(f"  Entities: {debit_entity.name}, {credit_entity.name}")

    # Stamp alembic version so restore works with dev_up.sh
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
        "note": "Empty DB with admin user, Scotiabank Debit/Credit accounts and entities only",
    }
    (SNAP_DIR / "metadata.json").write_text(json.dumps(meta, indent=2) + "\n")

    db.close()
    engine.dispose()


if __name__ == "__main__":
    main()
