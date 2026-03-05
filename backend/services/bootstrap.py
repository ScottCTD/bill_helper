from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import MetaData

from backend.models_finance import Account

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"
TSeedResult = TypeVar("TSeedResult")


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


def _build_alembic_config(*, database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI_PATH))
    cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    return cfg


def stamp_alembic_head_for_database_url(*, database_url: str) -> None:
    command.stamp(_build_alembic_config(database_url=database_url), "head")


def stamp_alembic_head_for_sqlite_path(db_path: Path) -> None:
    stamp_alembic_head_for_database_url(database_url=f"sqlite:///{db_path}")


def run_schema_seed_and_stamp(
    *,
    engine: Engine,
    metadata: MetaData,
    make_session: Callable[[], Session],
    seed: Callable[[Session], TSeedResult],
    recreate_schema: bool,
    stamp: Callable[[], None] | None = None,
) -> TSeedResult:
    """Canonical bootstrap contract: create schema -> seed -> stamp -> teardown."""
    if recreate_schema:
        metadata.drop_all(bind=engine)
    metadata.create_all(bind=engine)

    db = make_session()
    try:
        seed_result = seed(db)
        if stamp is not None:
            stamp()
        return seed_result
    finally:
        db.close()
        engine.dispose()
