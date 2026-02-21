"""remove institution and account_type from accounts

Revision ID: 0014_remove_account_institution_type
Revises: 0013_add_account_markdown_body
Create Date: 2026-02-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0014_remove_account_institution_type"
down_revision: str | Sequence[str] | None = "0013_add_account_markdown_body"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("institution")
        batch_op.drop_column("account_type")


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("institution", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("account_type", sa.String(length=100), nullable=True))
