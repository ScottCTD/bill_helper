"""convert accounts to shared entity-root subtype

Revision ID: 0024_entity_root_accounts
Revises: 0023_add_agent_provider_config
Create Date: 2026-03-06
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "0024_entity_root_accounts"
down_revision: str | None = "0023_add_agent_provider_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_name(raw: str | None, fallback: str) -> str:
    normalized = " ".join((raw or "").split()).strip()
    return normalized or fallback


def _entity_exists(bind: sa.engine.Connection, entity_id: str) -> bool:
    return (
        bind.execute(
            sa.text("SELECT id FROM entities WHERE id = :id LIMIT 1"),
            {"id": entity_id},
        ).scalar_one_or_none()
        is not None
    )


def _sync_entity_root(
    bind: sa.engine.Connection,
    *,
    entity_id: str,
    name: str,
    created_at: datetime,
    updated_at: datetime,
) -> None:
    if _entity_exists(bind, entity_id):
        bind.execute(
            sa.text(
                """
                UPDATE entities
                SET name = :name,
                    category = NULL,
                    updated_at = :updated_at
                WHERE id = :id
                """
            ),
            {
                "id": entity_id,
                "name": name,
                "updated_at": updated_at,
            },
        )
        return

    bind.execute(
        sa.text(
            """
            INSERT INTO entities (id, name, category, created_at, updated_at)
            VALUES (:id, :name, NULL, :created_at, :updated_at)
            """
        ),
        {
            "id": entity_id,
            "name": name,
            "created_at": created_at,
            "updated_at": updated_at,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError("Migration 0024 currently supports SQLite only.")

    bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        now = datetime.now(timezone.utc)
        account_rows = list(
            bind.execute(
                sa.text(
                    """
                    SELECT
                      id,
                      entity_id,
                      name,
                      owner_user_id,
                      markdown_body,
                      currency_code,
                      is_active,
                      created_at,
                      updated_at
                    FROM accounts
                    ORDER BY created_at ASC, id ASC
                    """
                )
            ).mappings()
        )

        account_id_map: dict[str, str] = {}
        rebuilt_rows: list[dict[str, object]] = []
        for row in account_rows:
            old_id = str(row["id"])
            candidate_entity_id = str(row["entity_id"]) if row["entity_id"] else None
            normalized_name = _normalize_name(str(row["name"]) if row["name"] is not None else None, f"account-{old_id[:8]}")
            new_id = candidate_entity_id if candidate_entity_id and _entity_exists(bind, candidate_entity_id) else old_id
            if new_id in account_id_map.values():
                raise RuntimeError(f"Cannot migrate duplicate account target id: {new_id}")

            created_at = row["created_at"] or now
            updated_at = row["updated_at"] or now
            _sync_entity_root(
                bind,
                entity_id=new_id,
                name=normalized_name,
                created_at=created_at,
                updated_at=updated_at,
            )

            account_id_map[old_id] = new_id
            rebuilt_rows.append(
                {
                    "id": new_id,
                    "owner_user_id": row["owner_user_id"],
                    "markdown_body": row["markdown_body"],
                    "currency_code": row["currency_code"],
                    "is_active": row["is_active"],
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

        for old_id, new_id in account_id_map.items():
            if old_id == new_id:
                continue
            bind.execute(
                sa.text("UPDATE entries SET account_id = :new_id WHERE account_id = :old_id"),
                {"old_id": old_id, "new_id": new_id},
            )
            bind.execute(
                sa.text("UPDATE account_snapshots SET account_id = :new_id WHERE account_id = :old_id"),
                {"old_id": old_id, "new_id": new_id},
            )

        entity_category_taxonomy_id = bind.execute(
            sa.text("SELECT id FROM taxonomies WHERE key = 'entity_category' LIMIT 1")
        ).scalar_one_or_none()
        if entity_category_taxonomy_id is not None and account_id_map:
            for entity_id in set(account_id_map.values()):
                bind.execute(
                    sa.text(
                        """
                        DELETE FROM taxonomy_assignments
                        WHERE taxonomy_id = :taxonomy_id
                          AND subject_type = 'entity'
                          AND subject_id = :subject_id
                        """
                    ),
                    {
                        "taxonomy_id": entity_category_taxonomy_id,
                        "subject_id": entity_id,
                    },
                )
        if account_id_map:
            for entity_id in set(account_id_map.values()):
                bind.execute(
                    sa.text("UPDATE entities SET category = NULL WHERE id = :id"),
                    {"id": entity_id},
                )

        op.create_table(
            "accounts_new",
            sa.Column(
                "id",
                sa.String(length=36),
                sa.ForeignKey("entities.id", ondelete="CASCADE"),
                primary_key=True,
                nullable=False,
            ),
            sa.Column("owner_user_id", sa.String(length=36), nullable=True),
            sa.Column("markdown_body", sa.Text(), nullable=True),
            sa.Column("currency_code", sa.String(length=3), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["owner_user_id"],
                ["users.id"],
                name="fk_accounts_owner_user_id_users",
                ondelete="SET NULL",
            ),
        )
        for row in rebuilt_rows:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO accounts_new
                      (id, owner_user_id, markdown_body, currency_code, is_active, created_at, updated_at)
                    VALUES
                      (:id, :owner_user_id, :markdown_body, :currency_code, :is_active, :created_at, :updated_at)
                    """
                ),
                row,
            )

        op.drop_table("accounts")
        op.rename_table("accounts_new", "accounts")
        op.create_index("ix_accounts_owner_user_id", "accounts", ["owner_user_id"])
        op.create_index("ix_accounts_currency_code", "accounts", ["currency_code"])
    finally:
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for migration 0024_entity_root_accounts.")
