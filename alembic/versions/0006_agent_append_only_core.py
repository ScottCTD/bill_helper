"""add agent append-only tables

Revision ID: 0006_agent_append_only_core
Revises: 0005_remove_attachments
Create Date: 2026-02-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_agent_append_only_core"
down_revision: str | None = "0005_remove_attachments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_threads",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "agent_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column(
            "role",
            sa.Enum("USER", "ASSISTANT", "SYSTEM", name="agentmessagerole"),
            nullable=False,
        ),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_threads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_messages_thread_id", "agent_messages", ["thread_id"], unique=False)
    op.create_index("ix_agent_messages_role", "agent_messages", ["role"], unique=False)

    op.create_table(
        "agent_message_attachments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["agent_messages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_message_attachments_message_id",
        "agent_message_attachments",
        ["message_id"],
        unique=False,
    )

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("user_message_id", sa.String(length=36), nullable=False),
        sa.Column("assistant_message_id", sa.String(length=36), nullable=True),
        sa.Column(
            "status",
            sa.Enum("RUNNING", "COMPLETED", "FAILED", name="agentrunstatus"),
            nullable=False,
        ),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["thread_id"], ["agent_threads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_message_id"], ["agent_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["agent_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_runs_thread_id", "agent_runs", ["thread_id"], unique=False)
    op.create_index("ix_agent_runs_user_message_id", "agent_runs", ["user_message_id"], unique=False)
    op.create_index("ix_agent_runs_assistant_message_id", "agent_runs", ["assistant_message_id"], unique=False)
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"], unique=False)

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("OK", "ERROR", name="agenttoolcallstatus"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"], unique=False)
    op.create_index("ix_agent_tool_calls_status", "agent_tool_calls", ["status"], unique=False)

    op.create_table(
        "agent_change_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "change_type",
            sa.Enum("CREATE_ENTRY", "CREATE_TAG", "CREATE_ENTITY", name="agentchangetype"),
            nullable=False,
        ),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("rationale_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING_REVIEW",
                "APPROVED",
                "REJECTED",
                "APPLIED",
                "APPLY_FAILED",
                name="agentchangestatus",
            ),
            nullable=False,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("applied_resource_type", sa.String(length=64), nullable=True),
        sa.Column("applied_resource_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_change_items_run_id", "agent_change_items", ["run_id"], unique=False)
    op.create_index("ix_agent_change_items_change_type", "agent_change_items", ["change_type"], unique=False)
    op.create_index("ix_agent_change_items_status", "agent_change_items", ["status"], unique=False)

    op.create_table(
        "agent_review_actions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_item_id", sa.String(length=36), nullable=False),
        sa.Column(
            "action",
            sa.Enum("APPROVE", "REJECT", name="agentreviewactiontype"),
            nullable=False,
        ),
        sa.Column("actor", sa.String(length=255), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["change_item_id"], ["agent_change_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_review_actions_change_item_id",
        "agent_review_actions",
        ["change_item_id"],
        unique=False,
    )
    op.create_index("ix_agent_review_actions_action", "agent_review_actions", ["action"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_review_actions_action", table_name="agent_review_actions")
    op.drop_index("ix_agent_review_actions_change_item_id", table_name="agent_review_actions")
    op.drop_table("agent_review_actions")

    op.drop_index("ix_agent_change_items_status", table_name="agent_change_items")
    op.drop_index("ix_agent_change_items_change_type", table_name="agent_change_items")
    op.drop_index("ix_agent_change_items_run_id", table_name="agent_change_items")
    op.drop_table("agent_change_items")

    op.drop_index("ix_agent_tool_calls_status", table_name="agent_tool_calls")
    op.drop_index("ix_agent_tool_calls_run_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")

    op.drop_index("ix_agent_runs_status", table_name="agent_runs")
    op.drop_index("ix_agent_runs_assistant_message_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_user_message_id", table_name="agent_runs")
    op.drop_index("ix_agent_runs_thread_id", table_name="agent_runs")
    op.drop_table("agent_runs")

    op.drop_index("ix_agent_message_attachments_message_id", table_name="agent_message_attachments")
    op.drop_table("agent_message_attachments")

    op.drop_index("ix_agent_messages_role", table_name="agent_messages")
    op.drop_index("ix_agent_messages_thread_id", table_name="agent_messages")
    op.drop_table("agent_messages")

    op.drop_table("agent_threads")
