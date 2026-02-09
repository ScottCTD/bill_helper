"""remove status from entries

Revision ID: 0009_remove_entry_status
Revises: 0008_agent_run_usage_metrics
Create Date: 2026-02-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_remove_entry_status"
down_revision: str | None = "0008_agent_run_usage_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


entry_status_enum = sa.Enum("CONFIRMED", "PENDING_REVIEW", name="entrystatus")


def upgrade() -> None:
    with op.batch_alter_table("entries") as batch_op:
        batch_op.drop_column("status")

    entry_status_enum.drop(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    entry_status_enum.create(op.get_bind(), checkfirst=True)

    with op.batch_alter_table("entries") as batch_op:
        batch_op.add_column(
            sa.Column(
                "status",
                entry_status_enum,
                nullable=False,
                server_default=sa.text("'CONFIRMED'"),
            )
        )

    op.execute(sa.text("UPDATE entries SET status = 'CONFIRMED' WHERE status IS NULL"))

    with op.batch_alter_table("entries") as batch_op:
        batch_op.alter_column("status", server_default=None)
