"""add context tokens to agent runs

Revision ID: 0021_add_agent_run_context_tokens
Revises: 0020_add_agent_message_attachment_original_filename
Create Date: 2026-03-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0021_add_agent_run_context_tokens"
down_revision: str | Sequence[str] | None = "0020_add_agent_message_attachment_original_filename"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_column("agent_runs", "context_tokens"):
        return
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("context_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    if not _has_column("agent_runs", "context_tokens"):
        return
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_column("context_tokens")
