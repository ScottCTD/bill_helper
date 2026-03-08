from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
from backend.services.agent.threads import THREAD_TITLE_MAX_LENGTH, validate_thread_title


class AgentThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class AgentThreadUpdate(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=THREAD_TITLE_MAX_LENGTH,
        description="Short thread title/topic in 1-5 words.",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return validate_thread_title(value)


class AgentThreadRead(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentThreadSummaryRead(AgentThreadRead):
    last_message_preview: str | None = None
    pending_change_count: int = 0
    has_running_run: bool = False


class AgentMessageAttachmentRead(BaseModel):
    id: str
    message_id: str
    mime_type: str
    file_path: str
    attachment_url: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentMessageRead(BaseModel):
    id: str
    thread_id: str
    role: AgentMessageRole
    content_markdown: str
    created_at: datetime
    attachments: list[AgentMessageAttachmentRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AgentToolCallRead(BaseModel):
    id: str
    run_id: str
    llm_tool_call_id: str | None = None
    tool_name: str
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    output_text: str | None = None
    has_full_payload: bool = False
    status: AgentToolCallStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AgentRunEventRead(BaseModel):
    id: str
    run_id: str
    sequence_index: int
    event_type: AgentRunEventType
    source: AgentRunEventSource | None = None
    message: str | None = None
    tool_call_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentReviewActionRead(BaseModel):
    id: str
    change_item_id: str
    action: AgentReviewActionType
    actor: str
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentChangeItemRead(BaseModel):
    id: str
    run_id: str
    change_type: AgentChangeType
    payload_json: dict[str, Any]
    rationale_text: str
    status: AgentChangeStatus
    review_note: str | None = None
    applied_resource_type: str | None = None
    applied_resource_id: str | None = None
    created_at: datetime
    updated_at: datetime
    review_actions: list[AgentReviewActionRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AgentRunRead(BaseModel):
    id: str
    thread_id: str
    user_message_id: str
    assistant_message_id: str | None = None
    terminal_assistant_reply: str | None = None
    status: AgentRunStatus
    model_name: str
    surface: str = "app"
    context_tokens: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    input_cost_usd: float | None = None
    output_cost_usd: float | None = None
    total_cost_usd: float | None = None
    error_text: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
    events: list[AgentRunEventRead] = Field(default_factory=list)
    tool_calls: list[AgentToolCallRead] = Field(default_factory=list)
    change_items: list[AgentChangeItemRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AgentThreadDetailRead(BaseModel):
    thread: AgentThreadRead
    messages: list[AgentMessageRead]
    runs: list[AgentRunRead]
    configured_model_name: str
    current_context_tokens: int | None = None


class AgentChangeItemApproveRequest(BaseModel):
    note: str | None = None
    payload_override: dict[str, Any] | None = None


class AgentChangeItemRejectRequest(BaseModel):
    note: str | None = None
    payload_override: dict[str, Any] | None = None


class AgentChangeItemReopenRequest(BaseModel):
    note: str | None = None
    payload_override: dict[str, Any] | None = None
