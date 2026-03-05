"""remove RELATED link type

Revision ID: 0012_remove_related_link_type
Revises: 0011_remove_openrouter_runtime_settings_fields
Create Date: 2026-02-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012_remove_related_link_type"
down_revision: str | Sequence[str] | None = "0011_remove_openrouter_runtime_settings_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

old_link_type_enum = sa.Enum("RECURRING", "SPLIT", "BUNDLE", "RELATED", name="linktype")
new_link_type_enum = sa.Enum("RECURRING", "SPLIT", "BUNDLE", name="linktype")


def upgrade() -> None:
    op.execute(sa.text("UPDATE entry_links SET link_type = 'BUNDLE' WHERE link_type = 'RELATED'"))
    with op.batch_alter_table("entry_links") as batch_op:
        batch_op.alter_column(
            "link_type",
            existing_type=old_link_type_enum,
            type_=new_link_type_enum,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("entry_links") as batch_op:
        batch_op.alter_column(
            "link_type",
            existing_type=new_link_type_enum,
            type_=old_link_type_enum,
            existing_nullable=False,
        )
