"""add original filename to agent attachments

Revision ID: 0020_add_agent_message_attachment_original_filename
Revises: 0019_add_transfer_entry_kind
Create Date: 2026-03-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0020_add_agent_message_attachment_original_filename"
down_revision: str | Sequence[str] | None = "0019_add_transfer_entry_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_column("agent_message_attachments", "original_filename"):
        return
    with op.batch_alter_table("agent_message_attachments") as batch_op:
        batch_op.add_column(sa.Column("original_filename", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    if not _has_column("agent_message_attachments", "original_filename"):
        return
    with op.batch_alter_table("agent_message_attachments") as batch_op:
        batch_op.drop_column("original_filename")
