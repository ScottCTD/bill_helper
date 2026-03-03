"""add description to tags

Revision ID: 0018_add_tag_description
Revises: 0017_rename_tag_category_taxonomy
Create Date: 2026-03-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0018_add_tag_description"
down_revision: str | Sequence[str] | None = "0017_rename_tag_category_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("tags") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("tags") as batch_op:
        batch_op.drop_column("description")
