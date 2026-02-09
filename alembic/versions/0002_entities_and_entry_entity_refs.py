"""add entities and entry entity references

Revision ID: 0002_entities_and_entry_entity_refs
Revises: 0001_initial
Create Date: 2026-02-08
"""

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0002_entities_and_entry_entity_refs"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_name(raw: str | None) -> str | None:
    if raw is None:
        return None
    normalized = " ".join(raw.split()).strip()
    return normalized or None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entities_name", "entities", ["name"], unique=True)

    with op.batch_alter_table("entries") as batch_op:
        batch_op.add_column(sa.Column("from_entity_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("to_entity_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("owner_entity_id", sa.String(length=36), nullable=True))
        batch_op.create_index("ix_entries_from_entity_id", ["from_entity_id"])
        batch_op.create_index("ix_entries_to_entity_id", ["to_entity_id"])
        batch_op.create_index("ix_entries_owner_entity_id", ["owner_entity_id"])
        batch_op.create_foreign_key(
            "fk_entries_from_entity_id_entities",
            "entities",
            ["from_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_entries_to_entity_id_entities",
            "entities",
            ["to_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "fk_entries_owner_entity_id_entities",
            "entities",
            ["owner_entity_id"],
            ["id"],
            ondelete="SET NULL",
        )

    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, from_entity, to_entity, owner FROM entries")
    ).mappings()

    entity_id_by_name: dict[str, str] = {}
    now = datetime.now(timezone.utc)

    def ensure_entity_id(name: str) -> str:
        lookup_key = name.lower()
        existing_id = entity_id_by_name.get(lookup_key)
        if existing_id is not None:
            return existing_id

        new_id = str(uuid4())
        bind.execute(
            sa.text(
                """
                INSERT INTO entities (id, name, created_at, updated_at)
                VALUES (:id, :name, :created_at, :updated_at)
                """
            ),
            {
                "id": new_id,
                "name": name,
                "created_at": now,
                "updated_at": now,
            },
        )
        entity_id_by_name[lookup_key] = new_id
        return new_id

    for row in rows:
        from_name = _normalize_name(row["from_entity"])
        to_name = _normalize_name(row["to_entity"])
        owner_name = _normalize_name(row["owner"])

        bind.execute(
            sa.text(
                """
                UPDATE entries
                SET
                  from_entity = :from_entity,
                  from_entity_id = :from_entity_id,
                  to_entity = :to_entity,
                  to_entity_id = :to_entity_id,
                  owner = :owner,
                  owner_entity_id = :owner_entity_id
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "from_entity": from_name,
                "from_entity_id": ensure_entity_id(from_name) if from_name else None,
                "to_entity": to_name,
                "to_entity_id": ensure_entity_id(to_name) if to_name else None,
                "owner": owner_name,
                "owner_entity_id": ensure_entity_id(owner_name) if owner_name else None,
            },
        )


def downgrade() -> None:
    with op.batch_alter_table("entries") as batch_op:
        batch_op.drop_constraint("fk_entries_owner_entity_id_entities", type_="foreignkey")
        batch_op.drop_constraint("fk_entries_to_entity_id_entities", type_="foreignkey")
        batch_op.drop_constraint("fk_entries_from_entity_id_entities", type_="foreignkey")
        batch_op.drop_index("ix_entries_owner_entity_id")
        batch_op.drop_index("ix_entries_to_entity_id")
        batch_op.drop_index("ix_entries_from_entity_id")
        batch_op.drop_column("owner_entity_id")
        batch_op.drop_column("to_entity_id")
        batch_op.drop_column("from_entity_id")

    op.drop_index("ix_entities_name", table_name="entities")
    op.drop_table("entities")
