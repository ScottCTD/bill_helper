"""add available agent models to runtime settings

Revision ID: 0028_add_available_agent_models_to_runtime_settings
Revises: 0027_add_agent_bulk_concurrency_setting
Create Date: 2026-03-08
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0028_add_available_agent_models_to_runtime_settings"
down_revision: str | None = "0027_add_agent_bulk_concurrency_setting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(sa.Column("available_agent_models", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("available_agent_models")