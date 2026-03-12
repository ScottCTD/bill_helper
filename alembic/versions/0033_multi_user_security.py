"""multi-user security and session auth

Revision ID: 0033_multi_user_security
Revises: 0032_add_filter_groups
Create Date: 2026-03-12
"""

from __future__ import annotations

from collections.abc import Sequence
import os

from alembic import op
import sqlalchemy as sa

from backend.services.passwords import password_reset_required_hash


revision: str = "0033_multi_user_security"
down_revision: str | None = "0032_add_filter_groups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

group_type_enum = sa.Enum("BUNDLE", "SPLIT", "RECURRING", name="grouptype")
entry_kind_enum = sa.Enum("EXPENSE", "INCOME", "TRANSFER", name="entrykind")
agent_message_role_enum = sa.Enum("user", "assistant", "system", name="agentmessagerole")
agent_run_status_enum = sa.Enum(
    "running",
    "completed",
    "failed",
    name="agentrunstatus",
)
agent_tool_call_status_enum = sa.Enum(
    "queued",
    "running",
    "ok",
    "error",
    "cancelled",
    name="agenttoolcallstatus",
)
agent_change_status_enum = sa.Enum(
    "PENDING_REVIEW",
    "APPROVED",
    "REJECTED",
    "APPLIED",
    "APPLY_FAILED",
    name="agentchangestatus",
)
agent_change_type_enum = sa.Enum(
    "create_entry",
    "update_entry",
    "delete_entry",
    "create_group",
    "update_group",
    "delete_group",
    "create_group_member",
    "delete_group_member",
    "create_tag",
    "update_tag",
    "delete_tag",
    "create_entity",
    "update_entity",
    "delete_entity",
    "create_account",
    "update_account",
    "delete_account",
    "create_snapshot",
    "delete_snapshot",
    name="agentchangetype",
)
agent_review_action_type_enum = sa.Enum(
    "approve",
    "reject",
    name="agentreviewactiontype",
)
agent_run_event_type_enum = sa.Enum(
    "run_started",
    "reasoning_update",
    "tool_call_queued",
    "tool_call_started",
    "tool_call_completed",
    "tool_call_failed",
    "tool_call_cancelled",
    "run_completed",
    "run_failed",
    name="agentruneventtype",
)
agent_run_event_source_enum = sa.Enum(
    "model_reasoning",
    "assistant_content",
    "tool_call",
    name="agentruneventsource",
)


def _table_row_count(bind: sa.engine.Connection, table_name: str) -> int:
    return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table_name}")).scalar_one() or 0)


def _user_row_count(bind: sa.engine.Connection) -> int:
    return _table_row_count(bind, "users")


def _null_owner_count(bind: sa.engine.Connection, table_name: str) -> int:
    return int(
        bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table_name} WHERE owner_user_id IS NULL")
        ).scalar_one()
        or 0
    )


def _resolve_owner_backfill_user_id(bind: sa.engine.Connection) -> str | None:
    configured_name = (os.getenv("BILL_HELPER_OWNER_BACKFILL_USER_NAME") or "").strip()
    if configured_name:
        configured_match = bind.execute(
            sa.text(
                """
                SELECT id
                FROM users
                WHERE lower(name) = lower(:name)
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            ),
            {"name": configured_name},
        ).scalar_one_or_none()
        if configured_match is not None:
            return str(configured_match)

    admin_match = bind.execute(
        sa.text(
            """
            SELECT id
            FROM users
            WHERE is_admin = 1
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if admin_match is not None:
        return str(admin_match)

    legacy_admin_match = bind.execute(
        sa.text(
            """
            SELECT id
            FROM users
            WHERE lower(name) = 'admin'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if legacy_admin_match is not None:
        return str(legacy_admin_match)
    return None


def _requires_owner_backfill(bind: sa.engine.Connection) -> bool:
    user_row_count = _user_row_count(bind)
    return any(
        (
            _table_row_count(bind, "entities") > 0,
            _table_row_count(bind, "tags") > 0,
            user_row_count > 0 and _table_row_count(bind, "taxonomies") > 0,
            _table_row_count(bind, "agent_threads") > 0,
            _null_owner_count(bind, "accounts") > 0,
            _null_owner_count(bind, "entries") > 0,
            _null_owner_count(bind, "entry_groups") > 0,
        )
    )


def _rebuild_users(bind: sa.engine.Connection) -> None:
    op.create_table(
        "users_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO users_new (id, name, password_hash, is_admin, created_at, updated_at)
            SELECT
              id,
              name,
              :password_hash,
              COALESCE(is_admin, 0),
              created_at,
              updated_at
            FROM users
            """
        ),
        {"password_hash": password_reset_required_hash()},
    )
    op.drop_table("users")
    op.rename_table("users_new", "users")
    op.create_index("ix_users_name", "users", ["name"], unique=True)


def _rebuild_accounts(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    op.create_table(
        "accounts_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("markdown_body", sa.Text(), nullable=True),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO accounts_new (id, owner_user_id, markdown_body, currency_code, is_active, created_at, updated_at)
            SELECT
              id,
              CASE
                WHEN owner_user_id IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE users.id = accounts.owner_user_id)
                  THEN owner_user_id
                ELSE :fallback_user_id
              END,
              markdown_body,
              currency_code,
              COALESCE(is_active, 1),
              created_at,
              updated_at
            FROM accounts
            """
        ),
        {"fallback_user_id": fallback_user_id},
    )
    op.drop_table("accounts")
    op.rename_table("accounts_new", "accounts")
    op.create_index("ix_accounts_owner_user_id", "accounts", ["owner_user_id"], unique=False)
    op.create_index("ix_accounts_currency_code", "accounts", ["currency_code"], unique=False)


def _rebuild_entries(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    op.create_table(
        "entries_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=True),
        sa.Column("kind", entry_kind_enum, nullable=False),
        sa.Column("occurred_at", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("from_entity_id", sa.String(length=36), nullable=True),
        sa.Column("to_entity_id", sa.String(length=36), nullable=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
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
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO entries_new
              (
                id, account_id, kind, occurred_at, name, amount_minor, currency_code,
                from_entity_id, to_entity_id, owner_user_id, from_entity, to_entity,
                owner, markdown_body, is_deleted, deleted_at, created_at, updated_at
              )
            SELECT
              entries.id,
              entries.account_id,
              entries.kind,
              entries.occurred_at,
              entries.name,
              entries.amount_minor,
              entries.currency_code,
              entries.from_entity_id,
              entries.to_entity_id,
              COALESCE(
                CASE
                  WHEN entries.owner_user_id IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE users.id = entries.owner_user_id)
                    THEN entries.owner_user_id
                END,
                (
                  SELECT users.id
                  FROM users
                  WHERE lower(users.name) = lower(trim(entries.owner))
                  ORDER BY users.created_at ASC, users.id ASC
                  LIMIT 1
                ),
                (
                  SELECT accounts.owner_user_id
                  FROM accounts
                  WHERE accounts.id = entries.account_id
                  LIMIT 1
                ),
                :fallback_user_id
              ),
              entries.from_entity,
              entries.to_entity,
              entries.owner,
              entries.markdown_body,
              COALESCE(entries.is_deleted, 0),
              entries.deleted_at,
              entries.created_at,
              entries.updated_at
            FROM entries
            """
        ),
        {"fallback_user_id": fallback_user_id},
    )
    op.drop_table("entries")
    op.rename_table("entries_new", "entries")
    op.create_index("ix_entries_account_id", "entries", ["account_id"], unique=False)
    op.create_index("ix_entries_kind", "entries", ["kind"], unique=False)
    op.create_index("ix_entries_occurred_at", "entries", ["occurred_at"], unique=False)
    op.create_index("ix_entries_currency_code", "entries", ["currency_code"], unique=False)
    op.create_index("ix_entries_from_entity_id", "entries", ["from_entity_id"], unique=False)
    op.create_index("ix_entries_to_entity_id", "entries", ["to_entity_id"], unique=False)
    op.create_index("ix_entries_owner_user_id", "entries", ["owner_user_id"], unique=False)
    op.create_index("ix_entries_is_deleted", "entries", ["is_deleted"], unique=False)


def _rebuild_entry_groups(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    op.create_table(
        "entry_groups_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("group_type", group_type_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO entry_groups_new (id, owner_user_id, name, group_type, created_at, updated_at)
            SELECT
              entry_groups.id,
              CASE
                WHEN entry_groups.owner_user_id IS NOT NULL AND EXISTS (SELECT 1 FROM users WHERE users.id = entry_groups.owner_user_id)
                  THEN entry_groups.owner_user_id
                WHEN 1 = (
                  SELECT COUNT(DISTINCT entries.owner_user_id)
                  FROM entry_group_members
                  JOIN entries ON entries.id = entry_group_members.entry_id
                  WHERE entry_group_members.group_id = entry_groups.id
                    AND entries.owner_user_id IS NOT NULL
                )
                  THEN (
                    SELECT MIN(entries.owner_user_id)
                    FROM entry_group_members
                    JOIN entries ON entries.id = entry_group_members.entry_id
                    WHERE entry_group_members.group_id = entry_groups.id
                      AND entries.owner_user_id IS NOT NULL
                  )
                ELSE :fallback_user_id
              END,
              entry_groups.name,
              entry_groups.group_type,
              entry_groups.created_at,
              entry_groups.updated_at
            FROM entry_groups
            """
        ),
        {"fallback_user_id": fallback_user_id},
    )
    op.drop_table("entry_groups")
    op.rename_table("entry_groups_new", "entry_groups")
    op.create_index("ix_entry_groups_owner_user_id", "entry_groups", ["owner_user_id"], unique=False)
    op.create_index("ix_entry_groups_group_type", "entry_groups", ["group_type"], unique=False)


def _rebuild_entities(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    op.create_table(
        "entities_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_entities_owner_name"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO entities_new (id, owner_user_id, name, category, created_at, updated_at)
            SELECT
              entities.id,
              CASE
                WHEN EXISTS (
                  SELECT 1
                  FROM accounts
                  WHERE accounts.id = entities.id
                    AND accounts.owner_user_id IS NOT NULL
                )
                  THEN (
                    SELECT accounts.owner_user_id
                    FROM accounts
                    WHERE accounts.id = entities.id
                    LIMIT 1
                  )
                WHEN 1 = (
                  SELECT COUNT(DISTINCT owner_id)
                  FROM (
                    SELECT entries.owner_user_id AS owner_id
                    FROM entries
                    WHERE entries.from_entity_id = entities.id
                      AND entries.owner_user_id IS NOT NULL
                    UNION
                    SELECT entries.owner_user_id AS owner_id
                    FROM entries
                    WHERE entries.to_entity_id = entities.id
                      AND entries.owner_user_id IS NOT NULL
                  )
                )
                  THEN (
                    SELECT MIN(owner_id)
                    FROM (
                      SELECT entries.owner_user_id AS owner_id
                      FROM entries
                      WHERE entries.from_entity_id = entities.id
                        AND entries.owner_user_id IS NOT NULL
                      UNION
                      SELECT entries.owner_user_id AS owner_id
                      FROM entries
                      WHERE entries.to_entity_id = entities.id
                        AND entries.owner_user_id IS NOT NULL
                    )
                  )
                ELSE :fallback_user_id
              END,
              entities.name,
              entities.category,
              entities.created_at,
              entities.updated_at
            FROM entities
            """
        ),
        {"fallback_user_id": fallback_user_id},
    )
    op.drop_table("entities")
    op.rename_table("entities_new", "entities")
    op.create_index("ix_entities_owner_user_id", "entities", ["owner_user_id"], unique=False)
    op.create_index("ix_entities_name", "entities", ["name"], unique=False)
    op.create_index("ix_entities_category", "entities", ["category"], unique=False)


def _rebuild_tags(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    op.create_table(
        "tags_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "name", name="uq_tags_owner_name"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO tags_new (id, owner_user_id, name, color, description, created_at)
            SELECT
              tags.id,
              CASE
                WHEN 1 = (
                  SELECT COUNT(DISTINCT entries.owner_user_id)
                  FROM entry_tags
                  JOIN entries ON entries.id = entry_tags.entry_id
                  WHERE entry_tags.tag_id = tags.id
                    AND entries.owner_user_id IS NOT NULL
                )
                  THEN (
                    SELECT MIN(entries.owner_user_id)
                    FROM entry_tags
                    JOIN entries ON entries.id = entry_tags.entry_id
                    WHERE entry_tags.tag_id = tags.id
                      AND entries.owner_user_id IS NOT NULL
                  )
                ELSE :fallback_user_id
              END,
              tags.name,
              tags.color,
              tags.description,
              tags.created_at
            FROM tags
            """
        ),
        {"fallback_user_id": fallback_user_id},
    )
    op.drop_table("tags")
    op.rename_table("tags_new", "tags")
    op.create_index("ix_tags_owner_user_id", "tags", ["owner_user_id"], unique=False)
    op.create_index("ix_tags_name", "tags", ["name"], unique=False)


def _rebuild_taxonomies(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    if fallback_user_id is None:
        bind.execute(sa.text("DELETE FROM taxonomy_assignments"))
        bind.execute(sa.text("DELETE FROM taxonomy_terms"))

    op.create_table(
        "taxonomies_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("applies_to", sa.String(length=50), nullable=False),
        sa.Column("cardinality", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_user_id", "key", name="uq_taxonomies_owner_key"),
    )
    if fallback_user_id is not None:
        bind.execute(
            sa.text(
                """
                INSERT INTO taxonomies_new
                  (id, owner_user_id, key, applies_to, cardinality, display_name, created_at, updated_at)
                SELECT
                  id,
                  :fallback_user_id,
                  key,
                  applies_to,
                  cardinality,
                  display_name,
                  created_at,
                  updated_at
                FROM taxonomies
                """
            ),
            {"fallback_user_id": fallback_user_id},
        )
    op.drop_table("taxonomies")
    op.rename_table("taxonomies_new", "taxonomies")
    op.create_index("ix_taxonomies_owner_user_id", "taxonomies", ["owner_user_id"], unique=False)
    op.create_index("ix_taxonomies_key", "taxonomies", ["key"], unique=False)


def _rebuild_agent_threads(bind: sa.engine.Connection, *, fallback_user_id: str | None) -> None:
    op.create_table(
        "agent_threads_new",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_user_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO agent_threads_new (id, owner_user_id, title, created_at, updated_at)
            SELECT
              id,
              :fallback_user_id,
              title,
              created_at,
              updated_at
            FROM agent_threads
            """
        ),
        {"fallback_user_id": fallback_user_id},
    )
    op.drop_table("agent_threads")
    op.rename_table("agent_threads_new", "agent_threads")
    op.create_index("ix_agent_threads_owner_user_id", "agent_threads", ["owner_user_id"], unique=False)


def _rebuild_runtime_settings() -> None:
    op.create_table(
        "runtime_settings_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("user_memory", sa.Text(), nullable=True),
        sa.Column("default_currency_code", sa.String(length=3), nullable=True),
        sa.Column("dashboard_currency_code", sa.String(length=3), nullable=True),
        sa.Column("agent_model", sa.String(length=255), nullable=True),
        sa.Column("available_agent_models", sa.Text(), nullable=True),
        sa.Column("agent_max_steps", sa.Integer(), nullable=True),
        sa.Column("agent_bulk_max_concurrent_threads", sa.Integer(), nullable=True),
        sa.Column("agent_retry_max_attempts", sa.Integer(), nullable=True),
        sa.Column("agent_retry_initial_wait_seconds", sa.Float(), nullable=True),
        sa.Column("agent_retry_max_wait_seconds", sa.Float(), nullable=True),
        sa.Column("agent_retry_backoff_multiplier", sa.Float(), nullable=True),
        sa.Column("agent_max_image_size_bytes", sa.Integer(), nullable=True),
        sa.Column("agent_max_images_per_message", sa.Integer(), nullable=True),
        sa.Column("agent_base_url", sa.String(length=500), nullable=True),
        sa.Column("agent_api_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope"),
    )
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            INSERT INTO runtime_settings_new
              (
                id, scope, user_memory, default_currency_code, dashboard_currency_code,
                agent_model, available_agent_models, agent_max_steps,
                agent_bulk_max_concurrent_threads, agent_retry_max_attempts,
                agent_retry_initial_wait_seconds, agent_retry_max_wait_seconds,
                agent_retry_backoff_multiplier, agent_max_image_size_bytes,
                agent_max_images_per_message, agent_base_url, agent_api_key,
                created_at, updated_at
              )
            SELECT
              id, scope, user_memory, default_currency_code, dashboard_currency_code,
              agent_model, available_agent_models, agent_max_steps,
              agent_bulk_max_concurrent_threads, agent_retry_max_attempts,
              agent_retry_initial_wait_seconds, agent_retry_max_wait_seconds,
              agent_retry_backoff_multiplier, agent_max_image_size_bytes,
              agent_max_images_per_message, agent_base_url, agent_api_key,
              created_at, updated_at
            FROM runtime_settings
            """
        )
    )
    op.drop_table("runtime_settings")
    op.rename_table("runtime_settings_new", "runtime_settings")


def _create_sessions_table() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_admin_impersonation", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        raise NotImplementedError("Migration 0033 currently supports SQLite only.")

    fallback_user_id = _resolve_owner_backfill_user_id(bind)
    if _requires_owner_backfill(bind) and fallback_user_id is None:
        raise RuntimeError(
            "Multi-user owner backfill requires an admin user or BILL_HELPER_OWNER_BACKFILL_USER_NAME."
        )

    bind.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        _rebuild_users(bind)
        _rebuild_accounts(bind, fallback_user_id=fallback_user_id)
        _rebuild_entries(bind, fallback_user_id=fallback_user_id)
        _rebuild_entry_groups(bind, fallback_user_id=fallback_user_id)
        _rebuild_entities(bind, fallback_user_id=fallback_user_id)
        _rebuild_tags(bind, fallback_user_id=fallback_user_id)
        _rebuild_taxonomies(bind, fallback_user_id=fallback_user_id)
        _rebuild_agent_threads(bind, fallback_user_id=fallback_user_id)
        _rebuild_runtime_settings()
        _create_sessions_table()
    finally:
        bind.exec_driver_sql("PRAGMA foreign_keys=ON")


def downgrade() -> None:
    raise NotImplementedError("Downgrade is not supported for migration 0033_multi_user_security.")
