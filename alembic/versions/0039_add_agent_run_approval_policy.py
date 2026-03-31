"""add agent run approval_policy

Revision ID: 0039_add_agent_run_approval_policy
Revises: 0038_add_agent_model_display_names_to_runtime_settings
Create Date: 2026-03-31
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0039_add_agent_run_approval_policy"
down_revision: str | None = "0038_add_agent_model_display_names_to_runtime_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "approval_policy",
                sa.String(length=32),
                nullable=False,
                server_default="default",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_column("approval_policy")
