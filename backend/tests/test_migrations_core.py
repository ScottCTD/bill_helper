from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"
ALEMBIC_SCRIPT_PATH = REPO_ROOT / "alembic"


def _build_alembic_config(database_url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI_PATH))
    cfg.set_main_option("sqlalchemy.url", database_url)
    cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_PATH))
    return cfg


def _sqlite_url(tmp_path: Path, name: str) -> str:
    return f"sqlite:///{tmp_path / name}"


def test_migration_0006_creates_agent_append_only_tables(tmp_path):
    database_url = _sqlite_url(tmp_path, "migration_0006.sqlite")
    command.upgrade(_build_alembic_config(database_url), "0006_agent_append_only_core")

    engine = create_engine(database_url, future=True)
    inspector = inspect(engine)
    assert {
        "agent_threads",
        "agent_messages",
        "agent_message_attachments",
        "agent_runs",
        "agent_tool_calls",
        "agent_change_items",
        "agent_review_actions",
    }.issubset(set(inspector.get_table_names()))

    run_indexes = {row["name"] for row in inspector.get_indexes("agent_runs")}
    assert {"ix_agent_runs_thread_id", "ix_agent_runs_status"}.issubset(run_indexes)


def test_migration_0007_backfills_entity_category_assignments(tmp_path):
    database_url = _sqlite_url(tmp_path, "migration_0007.sqlite")
    cfg = _build_alembic_config(database_url)
    command.upgrade(cfg, "0006_agent_append_only_core")

    now = datetime.now(timezone.utc)
    first_entity_id = str(uuid4())
    second_entity_id = str(uuid4())
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO entities (id, name, category, created_at, updated_at)
                VALUES (:id, :name, :category, :created_at, :updated_at)
                """
            ),
            {
                "id": first_entity_id,
                "name": "Groceries Vendor A",
                "category": " Daily  Expense ",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO entities (id, name, category, created_at, updated_at)
                VALUES (:id, :name, :category, :created_at, :updated_at)
                """
            ),
            {
                "id": second_entity_id,
                "name": "Groceries Vendor B",
                "category": "daily expense",
                "created_at": now,
                "updated_at": now,
            },
        )

    command.upgrade(cfg, "0007_taxonomy_core")
    with engine.begin() as connection:
        taxonomy_id = connection.execute(
            text("SELECT id FROM taxonomies WHERE key = 'entity_category' LIMIT 1")
        ).scalar_one()
        normalized_term_names = connection.execute(
            text(
                """
                SELECT normalized_name
                FROM taxonomy_terms
                WHERE taxonomy_id = :taxonomy_id
                """
            ),
            {"taxonomy_id": taxonomy_id},
        ).scalars()
        assignments = connection.execute(
            text(
                """
                SELECT subject_id
                FROM taxonomy_assignments
                WHERE taxonomy_id = :taxonomy_id
                """
            ),
            {"taxonomy_id": taxonomy_id},
        ).scalars()

        assert list(normalized_term_names) == ["daily expense"]
        assert set(assignments) == {first_entity_id, second_entity_id}


def test_migration_0017_renames_old_tag_taxonomy_when_new_key_missing(tmp_path):
    database_url = _sqlite_url(tmp_path, "migration_0017.sqlite")
    cfg = _build_alembic_config(database_url)
    command.upgrade(cfg, "0016_add_user_memory_to_runtime_settings")

    now = datetime.now(timezone.utc)
    old_taxonomy_id = str(uuid4())
    old_term_id = str(uuid4())
    old_assignment_id = str(uuid4())
    subject_id = str(uuid4())
    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        existing_new_taxonomy_id = connection.execute(
            text("SELECT id FROM taxonomies WHERE key = :key LIMIT 1"),
            {"key": "tag_type"},
        ).scalar_one_or_none()
        if existing_new_taxonomy_id is not None:
            connection.execute(
                text("DELETE FROM taxonomy_assignments WHERE taxonomy_id = :taxonomy_id"),
                {"taxonomy_id": existing_new_taxonomy_id},
            )
            connection.execute(
                text("DELETE FROM taxonomy_terms WHERE taxonomy_id = :taxonomy_id"),
                {"taxonomy_id": existing_new_taxonomy_id},
            )
            connection.execute(
                text("DELETE FROM taxonomies WHERE id = :taxonomy_id"),
                {"taxonomy_id": existing_new_taxonomy_id},
            )

        connection.execute(
            text(
                """
                INSERT INTO taxonomies (id, key, applies_to, cardinality, display_name, created_at, updated_at)
                VALUES (:id, :key, :applies_to, :cardinality, :display_name, :created_at, :updated_at)
                """
            ),
            {
                "id": old_taxonomy_id,
                "key": "tag_category",
                "applies_to": "tag",
                "cardinality": "single",
                "display_name": "Tag Categories",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO taxonomy_terms
                  (id, taxonomy_id, name, normalized_name, parent_term_id, metadata_json, created_at, updated_at)
                VALUES
                  (:id, :taxonomy_id, :name, :normalized_name, NULL, NULL, :created_at, :updated_at)
                """
            ),
            {
                "id": old_term_id,
                "taxonomy_id": old_taxonomy_id,
                "name": "Utilities",
                "normalized_name": "utilities",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO taxonomy_assignments
                  (id, taxonomy_id, term_id, subject_type, subject_id, position, created_at, updated_at)
                VALUES
                  (:id, :taxonomy_id, :term_id, :subject_type, :subject_id, 0, :created_at, :updated_at)
                """
            ),
            {
                "id": old_assignment_id,
                "taxonomy_id": old_taxonomy_id,
                "term_id": old_term_id,
                "subject_type": "tag",
                "subject_id": subject_id,
                "created_at": now,
                "updated_at": now,
            },
        )

    command.upgrade(cfg, "0017_rename_tag_category_taxonomy")
    with engine.begin() as connection:
        old_key_id = connection.execute(
            text("SELECT id FROM taxonomies WHERE key = :key LIMIT 1"),
            {"key": "tag_category"},
        ).scalar_one_or_none()
        new_taxonomy_row = connection.execute(
            text(
                """
                SELECT id, display_name
                FROM taxonomies
                WHERE key = :key
                LIMIT 1
                """
            ),
            {"key": "tag_type"},
        ).first()
        term_count = connection.execute(
            text("SELECT COUNT(*) FROM taxonomy_terms WHERE taxonomy_id = :taxonomy_id"),
            {"taxonomy_id": old_taxonomy_id},
        ).scalar_one()
        assignment_count = connection.execute(
            text("SELECT COUNT(*) FROM taxonomy_assignments WHERE taxonomy_id = :taxonomy_id"),
            {"taxonomy_id": old_taxonomy_id},
        ).scalar_one()

        assert old_key_id is None
        assert new_taxonomy_row is not None
        assert str(new_taxonomy_row[0]) == old_taxonomy_id
        assert str(new_taxonomy_row[1]) == "Tag Types"
        assert int(term_count) == 1
        assert int(assignment_count) == 1


def test_migration_chain_reaches_head_from_empty_database(tmp_path):
    database_url = _sqlite_url(tmp_path, "migration_head.sqlite")
    cfg = _build_alembic_config(database_url)
    command.upgrade(cfg, "head")

    engine = create_engine(database_url, future=True)
    with engine.begin() as connection:
        version_num = connection.execute(
            text("SELECT version_num FROM alembic_version LIMIT 1")
        ).scalar_one_or_none()
        assert isinstance(version_num, str)
        assert version_num
