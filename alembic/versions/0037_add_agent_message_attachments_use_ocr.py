"""add attachments_use_ocr to agent messages

Revision ID: 0037_add_agent_message_attachments_use_ocr
Revises: 0036_add_agent_run_created_at_index
Create Date: 2026-03-30 02:10:00.000000
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0037_add_agent_message_attachments_use_ocr"
down_revision: str | Sequence[str] | None = "0036_add_agent_run_created_at_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_messages",
        sa.Column("attachments_use_ocr", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("agent_messages", "attachments_use_ocr")
