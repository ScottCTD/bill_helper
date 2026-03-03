"""add TRANSFER to EntryKind enum

SQLite stores enums as plain strings, so no DDL change is needed.
This migration exists as documentation that TRANSFER is now a valid EntryKind value.

Revision ID: 0019_add_transfer_entry_kind
Revises: 0018_add_tag_description
Create Date: 2026-03-03
"""

from collections.abc import Sequence

revision: str = "0019_add_transfer_entry_kind"
down_revision: str | Sequence[str] | None = "0018_add_tag_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
