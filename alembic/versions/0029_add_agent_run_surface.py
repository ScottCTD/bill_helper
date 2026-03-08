"""add agent run surface

Revision ID: 0029_add_agent_run_surface
Revises: 0028_add_available_agent_models_to_runtime_settings
Create Date: 2026-03-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0029_add_agent_run_surface"
down_revision: str | Sequence[str] | None = "0028_add_available_agent_models_to_runtime_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column("surface", sa.String(length=32), nullable=False, server_default="app")
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_column("surface")
