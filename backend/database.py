from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import Settings, get_settings
from backend.db_meta import Base


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


# Backward-compatible alias for existing scripts/tests that import SessionLocal.
SessionLocal = get_session_maker()


def open_session() -> Session:
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    db = open_session()
    try:
        yield db
    finally:
        db.close()
