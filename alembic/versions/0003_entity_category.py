"""add entity category

Revision ID: 0003_entity_category
Revises: 0002_entities_and_entry_entity_refs
Create Date: 2026-02-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_entity_category"
down_revision: str | None = "0002_entities_and_entry_entity_refs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("entities") as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(length=100), nullable=True))
        batch_op.create_index("ix_entities_category", ["category"])


def downgrade() -> None:
    with op.batch_alter_table("entities") as batch_op:
        batch_op.drop_index("ix_entities_category")
        batch_op.drop_column("category")
