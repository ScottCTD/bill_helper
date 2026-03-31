"""add agent_model_display_names to runtime settings

Revision ID: 0038_add_agent_model_display_names_to_runtime_settings
Revises: 0037_add_agent_message_attachments_use_ocr
Create Date: 2026-03-30
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0038_add_agent_model_display_names_to_runtime_settings"
down_revision: str | None = "0037_add_agent_message_attachments_use_ocr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runtime_settings",
        sa.Column("agent_model_display_names", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("runtime_settings", "agent_model_display_names")
