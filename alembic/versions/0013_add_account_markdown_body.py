"""add markdown_body to accounts

Revision ID: 0013_add_account_markdown_body
Revises: 0012_remove_related_link_type
Create Date: 2026-02-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013_add_account_markdown_body"
down_revision: str | Sequence[str] | None = "0012_remove_related_link_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("markdown_body", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("markdown_body")
