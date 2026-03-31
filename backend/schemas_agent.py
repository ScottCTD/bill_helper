# CALLING SPEC:
# - Purpose: provide the `schemas_agent` module.
# - Inputs: callers that import `backend/schemas_agent.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `schemas_agent`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.enums_agent import (
    AgentApprovalPolicy,
    AgentChangeStatus,
    AgentChangeType,
    AgentMessageRole,
    AgentReviewActionType,
    AgentRunEventSource,
    AgentRunEventType,
    AgentRunStatus,
    AgentToolCallStatus,
)
from backend.validation.agent_threads import THREAD_TITLE_MAX_LENGTH, validate_thread_title


class AgentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AgentOrmReadSchema(AgentSchema):
    model_config = ConfigDict(extra="forbid", from_attributes=True)


class AgentThreadCreate(AgentSchema):
    title: str | None = Field(default=None, max_length=255)


class AgentThreadUpdate(AgentSchema):
    title: str = Field(
        min_length=1,
        max_length=THREAD_TITLE_MAX_LENGTH,
        description="Short thread title/topic in 1-5 words.",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return validate_thread_title(value)


class AgentThreadRead(AgentOrmReadSchema):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime

class AgentThreadSummaryRead(AgentThreadRead):
    last_message_preview: str | None = None
    pending_change_count: int = 0
    has_running_run: bool = False


class AgentMessageAttachmentRead(AgentOrmReadSchema):
    id: str
    message_id: str
    display_name: str
    mime_type: str
    file_path: str
    attachment_url: str
    created_at: datetime

class AgentDraftAttachmentRead(AgentOrmReadSchema):
    id: str
    display_name: str
    mime_type: str
    created_at: datetime

class AgentMessageRead(AgentOrmReadSchema):
    id: str
    thread_id: str
    role: AgentMessageRole
    content_markdown: str
    created_at: datetime
    attachments: list[AgentMessageAttachmentRead] = Field(default_factory=list)

class AgentToolCallRead(AgentOrmReadSchema):
    id: str
    run_id: str
    llm_tool_call_id: str | None = None
    tool_name: str
    display_label: str
    display_detail: str | None = None
    input_json: dict[str, Any] | None = None
    output_json: dict[str, Any] | None = None
    output_text: str | None = None
    has_full_payload: bool = False
    status: AgentToolCallStatus
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

class AgentRunEventRead(AgentOrmReadSchema):
    id: str
    run_id: str
    sequence_index: int
    event_type: AgentRunEventType
    source: AgentRunEventSource | None = None
    message: str | None = None
    tool_call_id: str | None = None
    created_at: datetime

class AgentReviewActionRead(AgentOrmReadSchema):
    id: str
    change_item_id: str
    action: AgentReviewActionType
    actor: str
    note: str | None = None
    created_at: datetime

class AgentChangeItemRead(AgentOrmReadSchema):
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

class AgentRunRead(AgentOrmReadSchema):
    id: str
    thread_id: str
    user_message_id: str
    assistant_message_id: str | None = None
    terminal_assistant_reply: str | None = None
    status: AgentRunStatus
    model_name: str
    approval_policy: AgentApprovalPolicy = AgentApprovalPolicy.DEFAULT
    surface: str = "app"
    reply_surface: str = "app"
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


class AgentDashboardMetricsRead(AgentSchema):
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_run_count: int = 0
    completed_run_count: int = 0
    failed_run_count: int = 0
    avg_cost_per_run_usd: float = 0.0
    avg_tokens_per_run: float = 0.0
    cache_hit_rate: float = 0.0
    most_used_model: str | None = None
    failure_rate: float = 0.0


class AgentDashboardCostPointRead(AgentSchema):
    bucket_key: str
    bucket_label: str
    bucket_start: datetime
    total_cost_usd: float = 0.0
    run_count: int = 0
    costs_by_model: dict[str, float] = Field(default_factory=dict)


class AgentDashboardTokenSliceRead(AgentSchema):
    label: str
    token_count: int
    share: float = 0.0


class AgentDashboardModelBreakdownRead(AgentSchema):
    model_name: str
    run_count: int = 0
    completed_run_count: int = 0
    failed_run_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    avg_cost_per_run_usd: float = 0.0


class AgentDashboardSurfaceBreakdownRead(AgentSchema):
    surface: str
    run_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    costs_by_model: dict[str, float] = Field(default_factory=dict)


class AgentDashboardTopRunRead(AgentSchema):
    run_id: str
    thread_id: str
    thread_title: str | None = None
    model_name: str
    surface: str
    status: AgentRunStatus
    created_at: datetime
    completed_at: datetime | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0


class AgentDashboardRead(AgentSchema):
    range_key: str
    granularity: str
    available_models: list[str] = Field(default_factory=list)
    available_surfaces: list[str] = Field(default_factory=list)
    selected_models: list[str] = Field(default_factory=list)
    selected_surfaces: list[str] = Field(default_factory=list)
    metrics: AgentDashboardMetricsRead
    cost_series: list[AgentDashboardCostPointRead] = Field(default_factory=list)
    token_distribution: list[AgentDashboardTokenSliceRead] = Field(default_factory=list)
    model_breakdown: list[AgentDashboardModelBreakdownRead] = Field(default_factory=list)
    surface_breakdown: list[AgentDashboardSurfaceBreakdownRead] = Field(default_factory=list)
    top_runs: list[AgentDashboardTopRunRead] = Field(default_factory=list)


class AgentThreadDetailRead(AgentSchema):
    thread: AgentThreadRead
    messages: list[AgentMessageRead]
    runs: list[AgentRunRead]
    configured_model_name: str
    current_context_tokens: int | None = None


class AgentChangeItemApproveRequest(AgentSchema):
    note: str | None = None
    payload_override: dict[str, Any] | None = None


class AgentChangeItemRejectRequest(AgentSchema):
    note: str | None = None
    payload_override: dict[str, Any] | None = None


class AgentChangeItemReopenRequest(AgentSchema):
    note: str | None = None
    payload_override: dict[str, Any] | None = None


class AgentProposalListQuery(AgentSchema):
    proposal_type: str | None = None
    proposal_status: AgentChangeStatus | None = None
    change_action: str | None = None
    proposal_id: str | None = Field(default=None, min_length=4, max_length=36)
    limit: int = Field(default=10, ge=1)


class AgentProposalCreateRequest(AgentSchema):
    change_type: AgentChangeType
    payload_json: dict[str, Any]


class AgentProposalUpdateRequest(AgentSchema):
    patch_map: dict[str, Any]


class AgentProposalRecordRead(AgentSchema):
    proposal_id: str
    proposal_short_id: str
    proposal_type: str
    change_action: str
    change_type: AgentChangeType
    status: AgentChangeStatus
    proposal_summary: str
    rationale_text: str
    payload: dict[str, Any]
    review_note: str | None = None
    applied_resource_type: str | None = None
    applied_resource_id: str | None = None
    created_at: datetime
    updated_at: datetime
    run_id: str
    review_actions: list[AgentReviewActionRead] = Field(default_factory=list)


class AgentProposalListRead(AgentSchema):
    returned_count: int
    total_available: int
    proposals: list[AgentProposalRecordRead]
