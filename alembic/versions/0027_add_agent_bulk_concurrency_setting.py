"""add agent bulk concurrency setting

Revision ID: 0027_add_agent_bulk_concurrency_setting
Revises: 0026_entry_groups_v2
Create Date: 2026-03-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0027_add_agent_bulk_concurrency_setting"
down_revision: str | Sequence[str] | None = "0026_entry_groups_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(
            sa.Column("agent_bulk_max_concurrent_threads", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("agent_bulk_max_concurrent_threads")
