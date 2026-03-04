"""add agent provider config

Revision ID: 0023_add_agent_provider_config
Revises: 0022_agent_run_events_and_tool_lifecycle
Create Date: 2026-03-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0023_add_agent_provider_config"
down_revision: str | Sequence[str] | None = "0022_agent_run_events_and_tool_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(
            sa.Column("agent_base_url", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("agent_api_key", sa.String(length=500), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("agent_api_key")
        batch_op.drop_column("agent_base_url")
