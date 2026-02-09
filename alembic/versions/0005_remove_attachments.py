"""remove attachments table

Revision ID: 0005_remove_attachments
Revises: 0004_users_and_account_entity_links
Create Date: 2026-02-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005_remove_attachments"
down_revision: str | None = "0004_users_and_account_entity_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_attachments_entry_id", table_name="attachments")
    op.drop_table("attachments")


def downgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("entry_id", sa.String(length=36), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attachments_entry_id", "attachments", ["entry_id"])
