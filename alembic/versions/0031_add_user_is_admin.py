"""add user is_admin column

Revision ID: 0031_add_user_is_admin
Revises: 0030_add_account_agent_change_types
Create Date: 2026-03-10
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0031_add_user_is_admin"
down_revision: str | None = "0030_add_account_agent_change_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" in existing_columns:
        return

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_admin",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_admin" not in existing_columns:
        return

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_admin")
