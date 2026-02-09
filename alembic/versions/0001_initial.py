"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


entry_kind_enum = sa.Enum("EXPENSE", "INCOME", name="entrykind")
entry_status_enum = sa.Enum("CONFIRMED", "PENDING_REVIEW", name="entrystatus")
link_type_enum = sa.Enum("RECURRING", "SPLIT", "BUNDLE", "RELATED", name="linktype")


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("institution", sa.String(length=200), nullable=True),
        sa.Column("account_type", sa.String(length=100), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_accounts_name", "accounts", ["name"])
    op.create_index("ix_accounts_currency_code", "accounts", ["currency_code"])

    op.create_table(
        "entry_groups",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tags_name", "tags", ["name"], unique=True)

    op.create_table(
        "entries",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("group_id", sa.String(length=36), sa.ForeignKey("entry_groups.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", entry_kind_enum, nullable=False),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("from_entity", sa.String(length=255), nullable=True),
        sa.Column("to_entity", sa.String(length=255), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("status", entry_status_enum, nullable=False),
        sa.Column("markdown_body", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entries_group_id", "entries", ["group_id"])
    op.create_index("ix_entries_account_id", "entries", ["account_id"])
    op.create_index("ix_entries_kind", "entries", ["kind"])
    op.create_index("ix_entries_occurred_at", "entries", ["occurred_at"])
    op.create_index("ix_entries_currency_code", "entries", ["currency_code"])
    op.create_index("ix_entries_is_deleted", "entries", ["is_deleted"])

    op.create_table(
        "account_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=36), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("snapshot_at", sa.Date(), nullable=False),
        sa.Column("balance_minor", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_account_snapshots_account_id", "account_snapshots", ["account_id"])
    op.create_index("ix_account_snapshots_snapshot_at", "account_snapshots", ["snapshot_at"])

    op.create_table(
        "entry_links",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("source_entry_id", sa.String(length=36), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_entry_id", sa.String(length=36), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("link_type", link_type_enum, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_entry_id", "target_entry_id", "link_type", name="uq_entry_links_tuple"),
    )
    op.create_index("ix_entry_links_source_entry_id", "entry_links", ["source_entry_id"])
    op.create_index("ix_entry_links_target_entry_id", "entry_links", ["target_entry_id"])
    op.create_index("ix_entry_links_link_type", "entry_links", ["link_type"])

    op.create_table(
        "entry_tags",
        sa.Column("entry_id", sa.String(length=36), sa.ForeignKey("entries.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("entry_id", sa.String(length=36), sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_attachments_entry_id", "attachments", ["entry_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_entry_id", table_name="attachments")
    op.drop_table("attachments")

    op.drop_table("entry_tags")

    op.drop_index("ix_entry_links_link_type", table_name="entry_links")
    op.drop_index("ix_entry_links_target_entry_id", table_name="entry_links")
    op.drop_index("ix_entry_links_source_entry_id", table_name="entry_links")
    op.drop_table("entry_links")

    op.drop_index("ix_account_snapshots_snapshot_at", table_name="account_snapshots")
    op.drop_index("ix_account_snapshots_account_id", table_name="account_snapshots")
    op.drop_table("account_snapshots")

    op.drop_index("ix_entries_is_deleted", table_name="entries")
    op.drop_index("ix_entries_currency_code", table_name="entries")
    op.drop_index("ix_entries_occurred_at", table_name="entries")
    op.drop_index("ix_entries_kind", table_name="entries")
    op.drop_index("ix_entries_account_id", table_name="entries")
    op.drop_index("ix_entries_group_id", table_name="entries")
    op.drop_table("entries")

    op.drop_index("ix_tags_name", table_name="tags")
    op.drop_table("tags")

    op.drop_table("entry_groups")

    op.drop_index("ix_accounts_currency_code", table_name="accounts")
    op.drop_index("ix_accounts_name", table_name="accounts")
    op.drop_table("accounts")

    link_type_enum.drop(op.get_bind(), checkfirst=True)
    entry_status_enum.drop(op.get_bind(), checkfirst=True)
    entry_kind_enum.drop(op.get_bind(), checkfirst=True)
