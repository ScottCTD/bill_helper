"""add output_text to agent_tool_calls

Revision ID: 0015_add_agent_tool_call_output_text
Revises: 0014_remove_account_institution_type
Create Date: 2026-02-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0015_add_agent_tool_call_output_text"
down_revision: str | Sequence[str] | None = "0014_remove_account_institution_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_tool_calls") as batch_op:
        batch_op.add_column(sa.Column("output_text", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("agent_tool_calls") as batch_op:
        batch_op.drop_column("output_text")
