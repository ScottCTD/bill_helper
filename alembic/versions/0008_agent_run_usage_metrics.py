"""add usage token fields to agent runs

Revision ID: 0008_agent_run_usage_metrics
Revises: 0007_taxonomy_core
Create Date: 2026-02-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_agent_run_usage_metrics"
down_revision: str | None = "0007_taxonomy_core"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("input_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("output_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("cache_read_tokens", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("cache_write_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "cache_write_tokens")
    op.drop_column("agent_runs", "cache_read_tokens")
    op.drop_column("agent_runs", "output_tokens")
    op.drop_column("agent_runs", "input_tokens")
