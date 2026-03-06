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


def test_migration_0024_rewrites_account_ids_to_entity_roots(tmp_path):
    database_url = _sqlite_url(tmp_path, "migration_0024.sqlite")
    cfg = _build_alembic_config(database_url)
    command.upgrade(cfg, "0023_add_agent_provider_config")

    engine = create_engine(database_url, future=True)
    now = datetime.now(timezone.utc)
    old_account_id = str(uuid4())
    account_entity_id = str(uuid4())
    group_id = str(uuid4())
    entry_id = str(uuid4())
    snapshot_id = str(uuid4())
    term_id = str(uuid4())
    assignment_id = str(uuid4())

    with engine.begin() as connection:
        taxonomy_id = connection.execute(
            text("SELECT id FROM taxonomies WHERE key = 'entity_category' LIMIT 1")
        ).scalar_one()
        connection.execute(
            text(
                """
                INSERT INTO entities (id, name, category, created_at, updated_at)
                VALUES (:id, :name, :category, :created_at, :updated_at)
                """
            ),
            {
                "id": account_entity_id,
                "name": "Primary Checking",
                "category": "cash account",
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
                "id": term_id,
                "taxonomy_id": taxonomy_id,
                "name": "cash account",
                "normalized_name": "cash account",
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
                  (:id, :taxonomy_id, :term_id, 'entity', :subject_id, 0, :created_at, :updated_at)
                """
            ),
            {
                "id": assignment_id,
                "taxonomy_id": taxonomy_id,
                "term_id": term_id,
                "subject_id": account_entity_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO accounts
                  (id, name, owner_user_id, entity_id, markdown_body, currency_code, is_active, created_at, updated_at)
                VALUES
                  (:id, :name, NULL, :entity_id, :markdown_body, :currency_code, :is_active, :created_at, :updated_at)
                """
            ),
            {
                "id": old_account_id,
                "name": "Primary Checking",
                "entity_id": account_entity_id,
                "markdown_body": "shared root migration",
                "currency_code": "USD",
                "is_active": 1,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO entry_groups (id, created_at, updated_at)
                VALUES (:id, :created_at, :updated_at)
                """
            ),
            {
                "id": group_id,
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO entries
                  (
                    id,
                    group_id,
                    account_id,
                    kind,
                    occurred_at,
                    name,
                    amount_minor,
                    currency_code,
                    from_entity_id,
                    to_entity_id,
                    owner_user_id,
                    from_entity,
                    to_entity,
                    owner,
                    markdown_body,
                    is_deleted,
                    deleted_at,
                    created_at,
                    updated_at
                  )
                VALUES
                  (
                    :id,
                    :group_id,
                    :account_id,
                    :kind,
                    :occurred_at,
                    :name,
                    :amount_minor,
                    :currency_code,
                    :from_entity_id,
                    NULL,
                    NULL,
                    :from_entity,
                    NULL,
                    'admin',
                    NULL,
                    0,
                    NULL,
                    :created_at,
                    :updated_at
                  )
                """
            ),
            {
                "id": entry_id,
                "group_id": group_id,
                "account_id": old_account_id,
                "kind": "EXPENSE",
                "occurred_at": "2026-03-01",
                "name": "Migrated rent",
                "amount_minor": 125000,
                "currency_code": "USD",
                "from_entity_id": account_entity_id,
                "from_entity": "Primary Checking",
                "created_at": now,
                "updated_at": now,
            },
        )
        connection.execute(
            text(
                """
                INSERT INTO account_snapshots
                  (id, account_id, snapshot_at, balance_minor, note, created_at)
                VALUES
                  (:id, :account_id, :snapshot_at, :balance_minor, :note, :created_at)
                """
            ),
            {
                "id": snapshot_id,
                "account_id": old_account_id,
                "snapshot_at": "2026-03-01",
                "balance_minor": 125000,
                "note": "pre-migration",
                "created_at": now,
            },
        )

    command.upgrade(cfg, "0024_entity_root_accounts")

    inspector = inspect(engine)
    account_columns = {column["name"] for column in inspector.get_columns("accounts")}
    assert "entity_id" not in account_columns
    assert "name" not in account_columns

    with engine.begin() as connection:
        account_row = connection.execute(
            text("SELECT id, markdown_body, currency_code, is_active FROM accounts LIMIT 1")
        ).mappings().one()
        entry_account_id = connection.execute(
            text("SELECT account_id FROM entries WHERE id = :id"),
            {"id": entry_id},
        ).scalar_one()
        snapshot_account_id = connection.execute(
            text("SELECT account_id FROM account_snapshots WHERE id = :id"),
            {"id": snapshot_id},
        ).scalar_one()
        entity_category = connection.execute(
            text("SELECT category FROM entities WHERE id = :id"),
            {"id": account_entity_id},
        ).scalar_one()
        assignment_count = connection.execute(
            text(
                """
                SELECT COUNT(*)
                FROM taxonomy_assignments
                WHERE subject_type = 'entity' AND subject_id = :subject_id
                """
            ),
            {"subject_id": account_entity_id},
        ).scalar_one()

        assert str(account_row["id"]) == account_entity_id
        assert str(entry_account_id) == account_entity_id
        assert str(snapshot_account_id) == account_entity_id
        assert str(account_row["markdown_body"]) == "shared root migration"
        assert str(account_row["currency_code"]) == "USD"
        assert int(account_row["is_active"]) == 1
        assert entity_category is None
        assert int(assignment_count) == 0
