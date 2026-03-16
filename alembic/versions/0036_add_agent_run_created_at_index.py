"""add created_at index for agent runs

Revision ID: 0036_add_agent_run_created_at_index
Revises: 0035_add_user_files_and_agent_workspace
Create Date: 2026-03-15 10:15:00.000000
"""

from __future__ import annotations

from typing import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0036_add_agent_run_created_at_index"
down_revision: str | Sequence[str] | None = "0035_add_user_files_and_agent_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
