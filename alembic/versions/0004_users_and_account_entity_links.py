"""add users and account-entity links; move entry owner to users

Revision ID: 0004_users_and_account_entity_links
Revises: 0003_entity_category
Create Date: 2026-02-08
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0004_users_and_account_entity_links"
down_revision: str | None = "0003_entity_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = " ".join(raw.split()).strip()
    return normalized or None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_name", "users", ["name"], unique=True)

    with op.batch_alter_table("entries") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_entries_owner_user_id", ["owner_user_id"])
        batch_op.create_foreign_key(
            "fk_entries_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("entity_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_accounts_owner_user_id", ["owner_user_id"])
        batch_op.create_index("ix_accounts_entity_id", ["entity_id"])
        batch_op.create_foreign_key(
            "fk_accounts_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_accounts_entity_id_entities",
            "entities",
            ["entity_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    user_id_by_name: dict[str, str] = {}

    def ensure_user_id(name: str) -> str:
        key = name.lower()
        existing = user_id_by_name.get(key)
        if existing is not None:
            return existing

        found = bind.execute(
            sa.text("SELECT id FROM users WHERE lower(name) = :name LIMIT 1"),
            {"name": key},
        ).scalar_one_or_none()
        if found is not None:
            user_id_by_name[key] = str(found)
            return str(found)

        user_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO users (id, name, created_at, updated_at)
                VALUES (:id, :name, :created_at, :updated_at)
                """
            ),
            {
                "id": user_id,
                "name": name,
                "created_at": now,
                "updated_at": now,
            },
        )
        user_id_by_name[key] = user_id
        return user_id

    owner_rows = bind.execute(sa.text("SELECT DISTINCT owner FROM entries")).scalars()
    for owner in owner_rows:
        normalized_owner = _normalize_name(owner)
        if normalized_owner:
            ensure_user_id(normalized_owner)

    current_user_name = "admin"
    current_user_id = ensure_user_id(current_user_name)

    entry_rows = bind.execute(
        sa.text("SELECT id, owner FROM entries")
    ).mappings()
    for row in entry_rows:
        normalized_owner = _normalize_name(row["owner"])
        owner_name = normalized_owner or current_user_name
        owner_user_id = ensure_user_id(owner_name)
        bind.execute(
            sa.text(
                """
                UPDATE entries
                SET owner = :owner, owner_user_id = :owner_user_id
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "owner": owner_name,
                "owner_user_id": owner_user_id,
            },
        )

    def ensure_account_entity_id(account_name: str, account_id: str) -> str:
        normalized_name = _normalize_name(account_name) or f"account-{account_id[:8]}"
        entity_row = bind.execute(
            sa.text("SELECT id, category FROM entities WHERE lower(name) = :name LIMIT 1"),
            {"name": normalized_name.lower()},
        ).mappings().first()
        if entity_row is not None:
            category = entity_row["category"]
            if category in (None, "account"):
                bind.execute(
                    sa.text("UPDATE entities SET category = 'account' WHERE id = :id"),
                    {"id": entity_row["id"]},
                )
                return str(entity_row["id"])

        candidate = normalized_name
        suffix = 1
        while bind.execute(
            sa.text("SELECT id FROM entities WHERE lower(name) = :name LIMIT 1"),
            {"name": candidate.lower()},
        ).scalar_one_or_none() is not None:
            candidate = f"{normalized_name} account {suffix}"
            suffix += 1

        entity_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO entities (id, name, category, created_at, updated_at)
                VALUES (:id, :name, :category, :created_at, :updated_at)
                """
            ),
            {
                "id": entity_id,
                "name": candidate,
                "category": "account",
                "created_at": now,
                "updated_at": now,
            },
        )
        return entity_id

    account_rows = bind.execute(
        sa.text("SELECT id, name FROM accounts")
    ).mappings()
    for row in account_rows:
        normalized_account_name = _normalize_name(row["name"]) or f"account-{row['id'][:8]}"
        entity_id = ensure_account_entity_id(normalized_account_name, row["id"])
        bind.execute(
            sa.text(
                """
                UPDATE accounts
                SET name = :name, entity_id = :entity_id, owner_user_id = :owner_user_id
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "name": normalized_account_name,
                "entity_id": entity_id,
                "owner_user_id": current_user_id,
            },
        )

    with op.batch_alter_table("entries") as batch_op:
        batch_op.drop_constraint("fk_entries_owner_entity_id_entities", type_="foreignkey")
        batch_op.drop_index("ix_entries_owner_entity_id")
        batch_op.drop_column("owner_entity_id")


def downgrade() -> None:
    with op.batch_alter_table("entries") as batch_op:
        batch_op.add_column(sa.Column("owner_entity_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_entries_owner_entity_id", ["owner_entity_id"])
        batch_op.create_foreign_key(
            "fk_entries_owner_entity_id_entities",
            "entities",
            ["owner_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    entity_id_by_name: dict[str, str] = {}

    def ensure_entity_id(name: str) -> str:
        key = name.lower()
        existing = entity_id_by_name.get(key)
        if existing is not None:
            return existing

        row = bind.execute(
            sa.text("SELECT id FROM entities WHERE lower(name) = :name LIMIT 1"),
            {"name": key},
        ).scalar_one_or_none()
        if row is not None:
            entity_id_by_name[key] = str(row)
            return str(row)

        entity_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO entities (id, name, created_at, updated_at)
                VALUES (:id, :name, :created_at, :updated_at)
                """
            ),
            {
                "id": entity_id,
                "name": name,
                "created_at": now,
                "updated_at": now,
            },
        )
        entity_id_by_name[key] = entity_id
        return entity_id

    rows = bind.execute(sa.text("SELECT id, owner FROM entries")).mappings()
    for row in rows:
        owner = _normalize_name(row["owner"])
        bind.execute(
            sa.text(
                """
                UPDATE entries
                SET owner_entity_id = :owner_entity_id
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "owner_entity_id": ensure_entity_id(owner) if owner else None,
            },
        )

    with op.batch_alter_table("entries") as batch_op:
        batch_op.drop_constraint("fk_entries_owner_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_entries_owner_user_id")
        batch_op.drop_column("owner_user_id")

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_constraint("fk_accounts_entity_id_entities", type_="foreignkey")
        batch_op.drop_constraint("fk_accounts_owner_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_accounts_entity_id")
        batch_op.drop_index("ix_accounts_owner_user_id")
        batch_op.drop_column("entity_id")
        batch_op.drop_column("owner_user_id")

    op.drop_index("ix_users_name", table_name="users")
    op.drop_table("users")
