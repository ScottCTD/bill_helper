# CALLING SPEC:
# - Purpose: provide the `models_agent` module.
# - Inputs: callers that import `backend/models_agent.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `models_agent`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db_meta import Base
from backend.enums_agent import (
    AgentChangeStatus,
    AgentChangeType,
    AgentMessageRole,
    AgentReviewActionType,
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
    AgentToolCallStatus,
)
from backend.models_shared import utc_now, uuid_str


class AgentThread(Base):
    __tablename__ = "agent_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    messages: Mapped[list[AgentMessage]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="AgentMessage.created_at",
    )
    runs: Mapped[list[AgentRun]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="AgentRun.created_at",
    )


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[AgentMessageRole] = mapped_column(
        Enum(AgentMessageRole), nullable=False, index=True
    )
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    thread: Mapped[AgentThread] = relationship(back_populates="messages")
    attachments: Mapped[list[AgentMessageAttachment]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="AgentMessageAttachment.created_at",
    )
    user_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="user_message",
        foreign_keys="AgentRun.user_message_id",
    )
    assistant_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="assistant_message",
        foreign_keys="AgentRun.assistant_message_id",
    )


class AgentMessageAttachment(Base):
    __tablename__ = "agent_message_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    message: Mapped[AgentMessage] = relationship(back_populates="attachments")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("agent_threads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_message_id: Mapped[str] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus), nullable=False, index=True
    )
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    surface: Mapped[str] = mapped_column(String(32), nullable=False, default="app")
    context_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    thread: Mapped[AgentThread] = relationship(back_populates="runs")
    user_message: Mapped[AgentMessage] = relationship(
        back_populates="user_runs", foreign_keys=[user_message_id]
    )
    assistant_message: Mapped[AgentMessage | None] = relationship(
        back_populates="assistant_runs",
        foreign_keys=[assistant_message_id],
    )
    tool_calls: Mapped[list[AgentToolCall]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentToolCall.created_at",
    )
    events: Mapped[list[AgentRunEvent]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentRunEvent.sequence_index",
    )
    change_items: Mapped[list[AgentChangeItem]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="AgentChangeItem.created_at",
    )


class AgentToolCall(Base):
    __tablename__ = "agent_tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    llm_tool_call_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentToolCallStatus] = mapped_column(
        Enum(AgentToolCallStatus), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    run: Mapped[AgentRun] = relationship(back_populates="tool_calls")
    events: Mapped[list[AgentRunEvent]] = relationship(back_populates="tool_call")


class AgentRunEvent(Base):
    __tablename__ = "agent_run_events"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "sequence_index", name="uq_agent_run_events_run_sequence"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[AgentRunEventType] = mapped_column(
        Enum(AgentRunEventType), nullable=False, index=True
    )
    source: Mapped[AgentRunEventSource | None] = mapped_column(
        Enum(AgentRunEventSource), nullable=True
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_tool_calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    run: Mapped[AgentRun] = relationship(back_populates="events")
    tool_call: Mapped[AgentToolCall | None] = relationship(back_populates="events")


class AgentChangeItem(Base):
    __tablename__ = "agent_change_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_type: Mapped[AgentChangeType] = mapped_column(
        Enum(AgentChangeType), nullable=False, index=True
    )
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rationale_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentChangeStatus] = mapped_column(
        Enum(AgentChangeStatus),
        nullable=False,
        default=AgentChangeStatus.PENDING_REVIEW,
        index=True,
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    applied_resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    run: Mapped[AgentRun] = relationship(back_populates="change_items")
    review_actions: Mapped[list[AgentReviewAction]] = relationship(
        back_populates="change_item",
        cascade="all, delete-orphan",
        order_by="AgentReviewAction.created_at",
    )


class AgentReviewAction(Base):
    __tablename__ = "agent_review_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    change_item_id: Mapped[str] = mapped_column(
        ForeignKey("agent_change_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[AgentReviewActionType] = mapped_column(
        Enum(AgentReviewActionType), nullable=False, index=True
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    change_item: Mapped[AgentChangeItem] = relationship(back_populates="review_actions")
