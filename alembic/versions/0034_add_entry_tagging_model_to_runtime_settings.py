"""add entry tagging model to runtime settings

Revision ID: 0034_add_entry_tagging_model_to_runtime_settings
Revises: 0033_multi_user_security
Create Date: 2026-03-12
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0034_add_entry_tagging_model_to_runtime_settings"
down_revision: str | None = "0033_multi_user_security"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(sa.Column("entry_tagging_model", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("entry_tagging_model")
