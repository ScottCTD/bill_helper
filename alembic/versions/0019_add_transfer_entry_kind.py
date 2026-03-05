"""add TRANSFER to EntryKind enum

SQLite stores enums as plain strings, so no DDL change is needed.
This migration exists as documentation that TRANSFER is now a valid EntryKind value.

Revision ID: 0019_add_transfer_entry_kind
Revises: 0018_add_tag_description
Create Date: 2026-03-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0019_add_transfer_entry_kind"
down_revision: str | Sequence[str] | None = "0018_add_tag_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _dialect_name() -> str:
    return op.get_bind().dialect.name


def upgrade() -> None:
    if _dialect_name() != "postgresql":
        return
    op.execute(sa.text("ALTER TYPE entrykind ADD VALUE IF NOT EXISTS 'TRANSFER'"))


def downgrade() -> None:
    if _dialect_name() != "postgresql":
        return

    op.execute(sa.text("UPDATE entries SET kind = 'EXPENSE' WHERE kind = 'TRANSFER'"))
    op.execute(sa.text("ALTER TYPE entrykind RENAME TO entrykind_old"))
    op.execute(sa.text("CREATE TYPE entrykind AS ENUM ('EXPENSE', 'INCOME')"))
    op.execute(
        sa.text(
            "ALTER TABLE entries ALTER COLUMN kind TYPE entrykind USING kind::text::entrykind"
        )
    )
    op.execute(sa.text("DROP TYPE entrykind_old"))
