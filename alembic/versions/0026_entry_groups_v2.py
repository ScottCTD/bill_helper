"""replace link-derived entry groups with typed groups

Revision ID: 0026_entry_groups_v2
Revises: 0025_user_memory_json_list
Create Date: 2026-03-07
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "0026_entry_groups_v2"
down_revision: str | None = "0025_user_memory_json_list"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

group_type_enum = sa.Enum("BUNDLE", "SPLIT", "RECURRING", name="grouptype")
group_member_role_enum = sa.Enum("PARENT", "CHILD", name="groupmemberrole")
entry_kind_enum = sa.Enum("EXPENSE", "INCOME", "TRANSFER", name="entrykind")


def _normalize_group_name(raw: str | None, fallback: str) -> str:
    normalized = " ".join((raw or "").split()).strip()
    return normalized or fallback


def _sorted_entries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            row["occurred_at"],
            row["created_at"],
            row["id"],
        ),
    )


def _infer_owner_user_id(rows: list[dict[str, object]]) -> str | None:
    owner_ids = {row["owner_user_id"] for row in rows if row["owner_user_id"] is not None}
    if len(owner_ids) == 1:
        return next(iter(owner_ids))
    if not owner_ids:
        return None
    return None


def _infer_group_type(rows: list[dict[str, object]], links: list[dict[str, object]]) -> tuple[str, dict[str, str | None]]:
    sorted_rows = _sorted_entries(rows)
    if not links:
        return "BUNDLE", {str(row["id"]): None for row in sorted_rows}

    link_types = {str(link["link_type"]) for link in links}
    if len(link_types) != 1:
        return "BUNDLE", {str(row["id"]): None for row in sorted_rows}

    inferred_type = next(iter(link_types))
    if inferred_type == "SPLIT":
        split_roles = _infer_split_roles(sorted_rows, links)
        if split_roles is not None:
            return "SPLIT", split_roles
        return "BUNDLE", {str(row["id"]): None for row in sorted_rows}

    if inferred_type == "RECURRING":
        recurring_order = _infer_recurring_order(sorted_rows, links)
        if recurring_order is not None:
            return "RECURRING", {entry_id: None for entry_id in recurring_order}
        return "BUNDLE", {str(row["id"]): None for row in sorted_rows}

    return "BUNDLE", {str(row["id"]): None for row in sorted_rows}


def _infer_split_roles(
    rows: list[dict[str, object]],
    links: list[dict[str, object]],
) -> dict[str, str] | None:
    if len(rows) < 2 or len(links) != len(rows) - 1:
        return None

    entry_ids = {str(row["id"]) for row in rows}
    outgoing: dict[str, set[str]] = defaultdict(set)
    incoming: dict[str, set[str]] = defaultdict(set)
    for link in links:
        source_entry_id = str(link["source_entry_id"])
        target_entry_id = str(link["target_entry_id"])
        if source_entry_id not in entry_ids or target_entry_id not in entry_ids:
            return None
        outgoing[source_entry_id].add(target_entry_id)
        incoming[target_entry_id].add(source_entry_id)

    root_candidates = [
        str(row["id"])
        for row in rows
        if len(outgoing.get(str(row["id"]), set())) == len(rows) - 1
        and len(incoming.get(str(row["id"]), set())) == 0
    ]
    if len(root_candidates) != 1:
        return None

    root_id = root_candidates[0]
    row_by_id = {str(row["id"]): row for row in rows}
    if str(row_by_id[root_id]["kind"]) != "EXPENSE":
        return None

    for row in rows:
        entry_id = str(row["id"])
        if entry_id == root_id:
            continue
        if incoming.get(entry_id) != {root_id} or outgoing.get(entry_id, set()):
            return None
        if str(row["kind"]) != "INCOME":
            return None

    roles = {entry_id: "CHILD" for entry_id in entry_ids}
    roles[root_id] = "PARENT"
    return roles


def _infer_recurring_order(
    rows: list[dict[str, object]],
    links: list[dict[str, object]],
) -> list[str] | None:
    if len(rows) < 2 or len(links) != len(rows) - 1:
        return None

    kinds = {str(row["kind"]) for row in rows}
    if len(kinds) != 1:
        return None

    ordered_rows = _sorted_entries(rows)
    expected_pairs = {
        (str(left["id"]), str(right["id"]))
        for left, right in zip(ordered_rows, ordered_rows[1:], strict=False)
    }
    actual_pairs = {
        (str(link["source_entry_id"]), str(link["target_entry_id"]))
        for link in links
    }
    if expected_pairs != actual_pairs:
        return None

    return [str(row["id"]) for row in ordered_rows]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError("Migration 0026 currently supports SQLite only.")

    bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        now = datetime.now(timezone.utc)
        group_rows = {
            str(row["id"]): dict(row)
            for row in bind.execute(
                sa.text(
                    """
                    SELECT id, created_at, updated_at
                    FROM entry_groups
                    """
                )
            ).mappings()
        }
        entry_rows = [dict(row) for row in bind.execute(sa.text("SELECT * FROM entries")).mappings()]
        entry_rows_by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
        non_deleted_group_by_entry_id: dict[str, str] = {}
        for row in entry_rows:
            group_id = row.get("group_id")
            if group_id is None or row.get("is_deleted"):
                continue
            normalized_group_id = str(group_id)
            entry_rows_by_group[normalized_group_id].append(row)
            non_deleted_group_by_entry_id[str(row["id"])] = normalized_group_id

        link_rows = [dict(row) for row in bind.execute(sa.text("SELECT * FROM entry_links")).mappings()]
        links_by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in link_rows:
            source_group_id = non_deleted_group_by_entry_id.get(str(row["source_entry_id"]))
            target_group_id = non_deleted_group_by_entry_id.get(str(row["target_entry_id"]))
            if source_group_id is None or source_group_id != target_group_id:
                continue
            links_by_group[source_group_id].append(row)

        migrated_group_rows: list[dict[str, object]] = []
        migrated_member_rows: list[dict[str, object]] = []

        for group_id, grouped_entries in entry_rows_by_group.items():
            if len(grouped_entries) < 2 and not links_by_group.get(group_id):
                continue

            sorted_entries = _sorted_entries(grouped_entries)
            group_type, role_map = _infer_group_type(sorted_entries, links_by_group.get(group_id, []))
            latest_entry = max(
                sorted_entries,
                key=lambda row: (row["occurred_at"], row["created_at"], row["id"]),
            )
            group_meta = group_rows.get(group_id, {})
            created_at = group_meta.get("created_at") or sorted_entries[0]["created_at"] or now
            updated_at = group_meta.get("updated_at") or latest_entry["updated_at"] or now
            migrated_group_rows.append(
                {
                    "id": group_id,
                    "owner_user_id": _infer_owner_user_id(sorted_entries),
                    "name": _normalize_group_name(
                        str(latest_entry["name"]) if latest_entry.get("name") is not None else None,
                        f"Group {group_id[:8]}",
                    ),
                    "group_type": group_type,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )

            if group_type == "SPLIT":
                ordered_entries = sorted(
                    sorted_entries,
                    key=lambda row: (
                        role_map.get(str(row["id"])) != "PARENT",
                        row["occurred_at"],
                        row["created_at"],
                        row["id"],
                    ),
                )
            else:
                ordered_entries = sorted_entries

            for position, entry_row in enumerate(ordered_entries):
                entry_id = str(entry_row["id"])
                migrated_member_rows.append(
                    {
                        "id": str(uuid4()),
                        "group_id": group_id,
                        "entry_id": entry_id,
                        "child_group_id": None,
                        "member_role": role_map.get(entry_id),
                        "position": position,
                        "created_at": entry_row.get("created_at") or created_at,
                        "updated_at": updated_at,
                    }
                )

        op.create_table(
            "entry_groups_new",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("owner_user_id", sa.String(length=36), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("group_type", group_type_enum, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["owner_user_id"],
                ["users.id"],
                name="fk_entry_groups_owner_user_id_users",
                ondelete="SET NULL",
            ),
        )
        op.create_table(
            "entries_new",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("account_id", sa.String(length=36), nullable=True),
            sa.Column("kind", entry_kind_enum, nullable=False),
            sa.Column("occurred_at", sa.Date(), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency_code", sa.String(length=3), nullable=False),
            sa.Column("from_entity_id", sa.String(length=36), nullable=True),
            sa.Column("to_entity_id", sa.String(length=36), nullable=True),
            sa.Column("owner_user_id", sa.String(length=36), nullable=True),
            sa.Column("from_entity", sa.String(length=255), nullable=True),
            sa.Column("to_entity", sa.String(length=255), nullable=True),
            sa.Column("owner", sa.String(length=255), nullable=True),
            sa.Column("markdown_body", sa.Text(), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["from_entity_id"], ["entities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["to_entity_id"], ["entities.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        )

        if entry_rows:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO entries_new
                      (
                        id,
                        account_id,
                        kind,
                        occurred_at,
                        name,
                        amount_minor,
                        currency_code,
                        from_entity_id,
                        to_entity_id,
                        owner_user_id,
                        from_entity,
                        to_entity,
                        owner,
                        markdown_body,
                        is_deleted,
                        deleted_at,
                        created_at,
                        updated_at
                      )
                    VALUES
                      (
                        :id,
                        :account_id,
                        :kind,
                        :occurred_at,
                        :name,
                        :amount_minor,
                        :currency_code,
                        :from_entity_id,
                        :to_entity_id,
                        :owner_user_id,
                        :from_entity,
                        :to_entity,
                        :owner,
                        :markdown_body,
                        :is_deleted,
                        :deleted_at,
                        :created_at,
                        :updated_at
                      )
                    """
                ),
                [
                    {
                        "id": row["id"],
                        "account_id": row["account_id"],
                        "kind": row["kind"],
                        "occurred_at": row["occurred_at"],
                        "name": row["name"],
                        "amount_minor": row["amount_minor"],
                        "currency_code": row["currency_code"],
                        "from_entity_id": row.get("from_entity_id"),
                        "to_entity_id": row.get("to_entity_id"),
                        "owner_user_id": row.get("owner_user_id"),
                        "from_entity": row.get("from_entity"),
                        "to_entity": row.get("to_entity"),
                        "owner": row.get("owner"),
                        "markdown_body": row.get("markdown_body"),
                        "is_deleted": row.get("is_deleted"),
                        "deleted_at": row.get("deleted_at"),
                        "created_at": row.get("created_at"),
                        "updated_at": row.get("updated_at"),
                    }
                    for row in entry_rows
                ],
            )

        if migrated_group_rows:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO entry_groups_new
                      (id, owner_user_id, name, group_type, created_at, updated_at)
                    VALUES
                      (:id, :owner_user_id, :name, :group_type, :created_at, :updated_at)
                    """
                ),
                migrated_group_rows,
            )

        op.drop_table("entry_links")
        op.drop_table("entries")
        op.drop_table("entry_groups")

        op.rename_table("entries_new", "entries")
        op.create_index("ix_entries_account_id", "entries", ["account_id"])
        op.create_index("ix_entries_kind", "entries", ["kind"])
        op.create_index("ix_entries_occurred_at", "entries", ["occurred_at"])
        op.create_index("ix_entries_currency_code", "entries", ["currency_code"])
        op.create_index("ix_entries_from_entity_id", "entries", ["from_entity_id"])
        op.create_index("ix_entries_to_entity_id", "entries", ["to_entity_id"])
        op.create_index("ix_entries_owner_user_id", "entries", ["owner_user_id"])
        op.create_index("ix_entries_is_deleted", "entries", ["is_deleted"])

        op.rename_table("entry_groups_new", "entry_groups")
        op.create_index("ix_entry_groups_owner_user_id", "entry_groups", ["owner_user_id"])
        op.create_index("ix_entry_groups_group_type", "entry_groups", ["group_type"])

        op.create_table(
            "entry_group_members",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("group_id", sa.String(length=36), nullable=False),
            sa.Column("entry_id", sa.String(length=36), nullable=True),
            sa.Column("child_group_id", sa.String(length=36), nullable=True),
            sa.Column("member_role", group_member_role_enum, nullable=True),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "(entry_id IS NOT NULL AND child_group_id IS NULL) OR "
                "(entry_id IS NULL AND child_group_id IS NOT NULL)",
                name="ck_entry_group_members_one_subject",
            ),
            sa.CheckConstraint(
                "child_group_id IS NULL OR group_id != child_group_id",
                name="ck_entry_group_members_no_self_child",
            ),
            sa.ForeignKeyConstraint(["group_id"], ["entry_groups.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["child_group_id"], ["entry_groups.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("group_id", "entry_id", name="uq_entry_group_members_group_entry"),
            sa.UniqueConstraint("group_id", "child_group_id", name="uq_entry_group_members_group_child"),
            sa.UniqueConstraint("entry_id", name="uq_entry_group_members_entry"),
            sa.UniqueConstraint("child_group_id", name="uq_entry_group_members_child_group"),
        )
        op.create_index("ix_entry_group_members_group_id", "entry_group_members", ["group_id"])
        op.create_index("ix_entry_group_members_entry_id", "entry_group_members", ["entry_id"])
        op.create_index("ix_entry_group_members_child_group_id", "entry_group_members", ["child_group_id"])
        op.create_index("ix_entry_group_members_member_role", "entry_group_members", ["member_role"])

        if migrated_member_rows:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO entry_group_members
                      (
                        id,
                        group_id,
                        entry_id,
                        child_group_id,
                        member_role,
                        position,
                        created_at,
                        updated_at
                      )
                    VALUES
                      (
                        :id,
                        :group_id,
                        :entry_id,
                        :child_group_id,
                        :member_role,
                        :position,
                        :created_at,
                        :updated_at
                      )
                    """
                ),
                migrated_member_rows,
            )
    finally:
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for migration 0026_entry_groups_v2.")
