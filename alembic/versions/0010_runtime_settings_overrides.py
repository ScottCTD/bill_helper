"""add runtime settings overrides

Revision ID: 0010_runtime_settings_overrides
Revises: 0009_remove_entry_status
Create Date: 2026-02-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010_runtime_settings_overrides"
down_revision: str | None = "0009_remove_entry_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("current_user_name", sa.String(length=255), nullable=True),
        sa.Column("default_currency_code", sa.String(length=3), nullable=True),
        sa.Column("dashboard_currency_code", sa.String(length=3), nullable=True),
        sa.Column("openrouter_api_key", sa.String(length=500), nullable=True),
        sa.Column("openrouter_base_url", sa.String(length=500), nullable=True),
        sa.Column("agent_model", sa.String(length=255), nullable=True),
        sa.Column("agent_max_steps", sa.Integer(), nullable=True),
        sa.Column("agent_retry_max_attempts", sa.Integer(), nullable=True),
        sa.Column("agent_retry_initial_wait_seconds", sa.Float(), nullable=True),
        sa.Column("agent_retry_max_wait_seconds", sa.Float(), nullable=True),
        sa.Column("agent_retry_backoff_multiplier", sa.Float(), nullable=True),
        sa.Column("agent_max_image_size_bytes", sa.Integer(), nullable=True),
        sa.Column("agent_max_images_per_message", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", name="uq_runtime_settings_scope"),
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
