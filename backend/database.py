# CALLING SPEC:
# - Purpose: provide the `database` module.
# - Inputs: callers that import `backend/database.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `database`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import Settings, get_settings
from backend.db_meta import Base
import backend.models_agent  # noqa: F401
import backend.models_files  # noqa: F401
import backend.models_finance  # noqa: F401
import backend.models_settings  # noqa: F401


def _sqlite_connect_args(database_url: str) -> dict[str, object]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def build_engine_for_url(database_url: str) -> Engine:
    return create_engine(
        database_url,
        future=True,
        connect_args=_sqlite_connect_args(database_url),
    )


def build_engine(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or get_settings()
    return build_engine_for_url(resolved_settings.database_url)


def build_session_maker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return build_engine()


@lru_cache(maxsize=1)
def get_session_maker() -> sessionmaker[Session]:
    return build_session_maker(get_engine())


class _SessionLocalProxy:
    def __call__(self) -> Session:
        return get_session_maker()()


# Backward-compatible callable alias for existing scripts/tests that import SessionLocal.
SessionLocal = _SessionLocalProxy()


def open_session() -> Session:
    return get_session_maker()()


def get_db() -> Generator[Session, None, None]:
    db = open_session()
    try:
        yield db
    finally:
        db.close()
