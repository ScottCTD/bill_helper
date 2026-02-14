"""remove openrouter runtime setting fields

Revision ID: 0011_remove_openrouter_runtime_settings_fields
Revises: 0010_runtime_settings_overrides
Create Date: 2026-02-14 21:05:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_remove_openrouter_runtime_settings_fields"
down_revision: str | Sequence[str] | None = "0010_runtime_settings_overrides"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.drop_column("openrouter_api_key")
        batch_op.drop_column("openrouter_base_url")


def downgrade() -> None:
    with op.batch_alter_table("runtime_settings") as batch_op:
        batch_op.add_column(sa.Column("openrouter_base_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("openrouter_api_key", sa.String(length=500), nullable=True))
