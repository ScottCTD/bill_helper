"""add agent run events and tool lifecycle fields

Revision ID: 0022_agent_run_events_and_tool_lifecycle
Revises: 0021_add_agent_run_context_tokens
Create Date: 2026-03-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0022_agent_run_events_and_tool_lifecycle"
down_revision: str | Sequence[str] | None = "0021_add_agent_run_context_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


old_tool_status = sa.Enum("OK", "ERROR", name="agenttoolcallstatus")
new_tool_status = sa.Enum("QUEUED", "RUNNING", "OK", "ERROR", "CANCELLED", name="agenttoolcallstatus")
run_event_type = sa.Enum(
    "RUN_STARTED",
    "REASONING_UPDATE",
    "TOOL_CALL_QUEUED",
    "TOOL_CALL_STARTED",
    "TOOL_CALL_COMPLETED",
    "TOOL_CALL_FAILED",
    "TOOL_CALL_CANCELLED",
    "RUN_COMPLETED",
    "RUN_FAILED",
    name="agentruneventtype",
)
run_event_source = sa.Enum(
    "MODEL_REASONING",
    "ASSISTANT_CONTENT",
    "TOOL_CALL",
    name="agentruneventsource",
)


def upgrade() -> None:
    with op.batch_alter_table("agent_tool_calls") as batch_op:
        batch_op.add_column(sa.Column("llm_tool_call_id", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.alter_column(
            "status",
            existing_type=old_tool_status,
            type_=new_tool_status,
            existing_nullable=False,
        )

    op.create_index("ix_agent_tool_calls_llm_tool_call_id", "agent_tool_calls", ["llm_tool_call_id"], unique=False)
    op.execute("UPDATE agent_tool_calls SET started_at = created_at, completed_at = created_at")

    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence_index", sa.Integer(), nullable=False),
        sa.Column("event_type", run_event_type, nullable=False),
        sa.Column("source", run_event_source, nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("tool_call_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_call_id"], ["agent_tool_calls.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence_index", name="uq_agent_run_events_run_sequence"),
    )
    op.create_index("ix_agent_run_events_run_id", "agent_run_events", ["run_id"], unique=False)
    op.create_index("ix_agent_run_events_event_type", "agent_run_events", ["event_type"], unique=False)
    op.create_index("ix_agent_run_events_tool_call_id", "agent_run_events", ["tool_call_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_run_events_tool_call_id", table_name="agent_run_events")
    op.drop_index("ix_agent_run_events_event_type", table_name="agent_run_events")
    op.drop_index("ix_agent_run_events_run_id", table_name="agent_run_events")
    op.drop_table("agent_run_events")

    op.drop_index("ix_agent_tool_calls_llm_tool_call_id", table_name="agent_tool_calls")
    with op.batch_alter_table("agent_tool_calls") as batch_op:
        batch_op.alter_column(
            "status",
            existing_type=new_tool_status,
            type_=old_tool_status,
            existing_nullable=False,
        )
        batch_op.drop_column("completed_at")
        batch_op.drop_column("started_at")
        batch_op.drop_column("llm_tool_call_id")
