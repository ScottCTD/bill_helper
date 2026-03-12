from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.database import build_engine, build_session_maker
from backend.db_meta import Base
from backend.models_finance import Account, Entity, User
from backend.services.bootstrap import (
    run_schema_seed_and_stamp,
    should_seed_demo_data,
    should_stamp_existing_schema,
)

engine = build_engine()
SessionLocal = build_session_maker(engine)


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_should_seed_demo_data_when_accounts_table_is_empty(db_session):
    assert should_seed_demo_data(db_session) is True


def test_should_not_seed_demo_data_when_account_exists(db_session):
    owner = db_session.query(User).filter(User.name == "admin").one()
    entity = Entity(name="Existing Account", category=None, owner_user_id=owner.id)
    db_session.add(entity)
    db_session.flush()
    db_session.add(
        Account(
            id=entity.id,
            owner_user_id=owner.id,
            currency_code="CAD",
            is_active=True,
        )
    )
    db_session.commit()

    assert should_seed_demo_data(db_session) is False


def test_should_stamp_existing_schema_when_app_tables_exist_without_alembic_version(db_session):
    db_session.execute(text("DROP TABLE IF EXISTS alembic_version"))
    db_session.commit()

    assert should_stamp_existing_schema(db_session) is True


def test_should_not_stamp_existing_schema_when_database_has_no_app_tables(db_session):
    Base.metadata.drop_all(bind=engine)

    assert should_stamp_existing_schema(db_session) is False


def test_should_stamp_existing_schema_when_alembic_version_table_is_empty(db_session):
    db_session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
    db_session.execute(text("DELETE FROM alembic_version"))
    db_session.commit()

    assert should_stamp_existing_schema(db_session) is True


def test_should_not_stamp_existing_schema_when_alembic_version_has_revision(db_session):
    db_session.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY)"))
    db_session.execute(text("DELETE FROM alembic_version"))
    db_session.execute(text("INSERT INTO alembic_version(version_num) VALUES ('0009_remove_entry_status')"))
    db_session.commit()

    assert should_stamp_existing_schema(db_session) is False


def test_run_schema_seed_and_stamp_calls_seed_then_stamp():
    metadata = MetaData()
    markers = Table("markers", metadata, Column("id", Integer, primary_key=True))
    local_engine = create_engine("sqlite:///:memory:", future=True)
    make_session = sessionmaker(bind=local_engine, class_=Session)
    events: list[str] = []

    def seed(db: Session) -> str:
        db.execute(markers.insert().values(id=1))
        db.commit()
        events.append("seed")
        return "ok"

    def stamp() -> None:
        events.append("stamp")

    result = run_schema_seed_and_stamp(
        engine=local_engine,
        metadata=metadata,
        make_session=make_session,
        seed=seed,
        recreate_schema=False,
        stamp=stamp,
    )

    assert result == "ok"
    assert events == ["seed", "stamp"]


def test_run_schema_seed_and_stamp_recreate_schema_drops_existing_rows():
    metadata = MetaData()
    markers = Table("markers", metadata, Column("id", Integer, primary_key=True))
    local_engine = create_engine("sqlite:///:memory:", future=True)
    metadata.create_all(bind=local_engine)

    initial_session = sessionmaker(bind=local_engine, class_=Session)()
    initial_session.execute(markers.insert().values(id=1))
    initial_session.commit()
    initial_session.close()

    make_session = sessionmaker(bind=local_engine, class_=Session)

    def seed(db: Session) -> int:
        existing = db.scalar(text("SELECT COUNT(*) FROM markers"))
        db.execute(markers.insert().values(id=2))
        db.commit()
        return int(existing or 0)

    existing_count_before_seed = run_schema_seed_and_stamp(
        engine=local_engine,
        metadata=metadata,
        make_session=make_session,
        seed=seed,
        recreate_schema=True,
        stamp=None,
    )

    assert existing_count_before_seed == 0


def test_bootstrap_admin_script_creates_admin_in_isolated_data_dir(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = tmp_path / "data"
    env = {
        **dict(os.environ),
        "BILL_HELPER_DATA_DIR": str(data_dir),
    }
    env.pop("BILL_HELPER_DATABASE_URL", None)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/bootstrap_admin.py",
            "--name",
            "script-admin",
            "--password",
            "script-password",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Admin user ready: script-admin" in result.stdout

    verification_engine = create_engine(
        f"sqlite:///{data_dir / 'bill_helper.db'}",
        future=True,
    )
    with verification_engine.connect() as connection:
        user = connection.execute(
            text("SELECT name, is_admin, password_hash FROM users WHERE name = 'script-admin'")
        ).mappings().one()

    assert user["name"] == "script-admin"
    assert user["is_admin"] == 1
    assert user["password_hash"]
