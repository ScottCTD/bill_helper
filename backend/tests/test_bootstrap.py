from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.database import Base, SessionLocal, engine
from backend.models import Account
from backend.services.bootstrap import should_seed_demo_data, should_stamp_existing_schema


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
    db_session.add(
        Account(
            name="Existing Account",
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
