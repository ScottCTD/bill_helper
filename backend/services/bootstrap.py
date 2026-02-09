from __future__ import annotations

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from backend.models import Account


def should_seed_demo_data(db: Session) -> bool:
    """Return True when the app database has no accounts yet."""
    first_account_id = db.scalar(select(Account.id).limit(1))
    return first_account_id is None


def should_stamp_existing_schema(db: Session) -> bool:
    """Return True when app tables exist but Alembic revision metadata is missing."""
    table_names = set(inspect(db.get_bind()).get_table_names())
    if "accounts" not in table_names:
        return False
    if "alembic_version" not in table_names:
        return True

    current_revision = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    return current_revision is None
