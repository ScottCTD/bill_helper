"""add user_memory to runtime_settings

Revision ID: 0016_add_user_memory_to_runtime_settings
Revises: 0015_add_agent_tool_call_output_text
Create Date: 2026-02-27
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0016_add_user_memory_to_runtime_settings"
down_revision: str | Sequence[str] | None = "0015_add_agent_tool_call_output_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(sa.Column("user_memory", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("user_memory")
