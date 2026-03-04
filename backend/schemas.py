from __future__ import annotations

from datetime import date, datetime
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.enums import (
    AgentChangeStatus,
    AgentChangeType,
    AgentMessageRole,
    AgentRunEventSource,
    AgentRunEventType,
    AgentReviewActionType,
    AgentRunStatus,
    AgentToolCallStatus,
    EntryKind,
    LinkType,
)


class TagRead(BaseModel):
    id: int
    name: str
    color: str | None = None
    description: str | None = None
    type: str | None = None
    entry_count: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    type: str | None = Field(default=None, max_length=100)


class TagUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    type: str | None = Field(default=None, max_length=100)


class EntityRead(BaseModel):
    id: str
    name: str
    category: str | None = None
    from_count: int | None = None
    to_count: int | None = None
    account_count: int | None = None
    entry_count: int | None = None

    model_config = ConfigDict(from_attributes=True)


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)


class EntityUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    id: str
    name: str
    is_current_user: bool = False
    account_count: int | None = None
    entry_count: int | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class CurrencyRead(BaseModel):
    code: str = Field(min_length=3, max_length=3)
    name: str
    entry_count: int
    is_placeholder: bool


class TaxonomyRead(BaseModel):
    id: str
    key: str
    applies_to: str
    cardinality: str
    display_name: str

    model_config = ConfigDict(from_attributes=True)


class TaxonomyTermCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_term_id: str | None = None
    description: str | None = Field(default=None, max_length=2000)


class TaxonomyTermUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class TaxonomyTermRead(BaseModel):
    id: str
    taxonomy_id: str
    name: str
    normalized_name: str
    parent_term_id: str | None = None
    description: str | None = None
    usage_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class AccountBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: str = Field(min_length=3, max_length=3)


class AccountCreate(AccountBase):
    owner_user_id: str | None = None
    is_active: bool = True


class AccountUpdate(BaseModel):
    owner_user_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


class AccountRead(AccountBase):
    id: str
    owner_user_id: str | None = None
    entity_id: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SnapshotCreate(BaseModel):
    snapshot_at: date
    balance_minor: int
    note: str | None = None


class SnapshotRead(BaseModel):
    id: str
    account_id: str
    snapshot_at: date
    balance_minor: int
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationRead(BaseModel):
    account_id: str
    account_name: str
    currency_code: str
    as_of: date
    ledger_balance_minor: int
    snapshot_balance_minor: int | None = None
    snapshot_at: date | None = None
    delta_minor: int | None = None


class LinkCreate(BaseModel):
    target_entry_id: str
    link_type: LinkType
    note: str | None = None


class LinkRead(BaseModel):
    id: str
    source_entry_id: str
    target_entry_id: str
    link_type: LinkType
    note: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntryBase(BaseModel):
    account_id: str | None = None
    kind: EntryKind
    occurred_at: date
    name: str = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    owner_user_id: str | None = None
    from_entity: str | None = Field(default=None, max_length=255)
    to_entity: str | None = Field(default=None, max_length=255)
    owner: str | None = Field(default=None, max_length=255)
    markdown_body: str | None = None


class EntryCreate(EntryBase):
    tags: list[str] = Field(default_factory=list)


class EntryUpdate(BaseModel):
    account_id: str | None = None
    kind: EntryKind | None = None
    occurred_at: date | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount_minor: int | None = Field(default=None, gt=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    owner_user_id: str | None = None
    from_entity: str | None = Field(default=None, max_length=255)
    to_entity: str | None = Field(default=None, max_length=255)
    owner: str | None = Field(default=None, max_length=255)
    markdown_body: str | None = None
    tags: list[str] | None = None


class EntryRead(BaseModel):
    id: str
    group_id: str
    account_id: str | None = None
    kind: EntryKind
    occurred_at: date
    name: str
    amount_minor: int
    currency_code: str
    from_entity_id: str | None = None
    to_entity_id: str | None = None
    owner_user_id: str | None = None
    from_entity: str | None = None
    to_entity: str | None = None
    owner: str | None = None
    markdown_body: str | None = None
    created_at: datetime
    updated_at: datetime
    tags: list[TagRead] = Field(default_factory=list)


class EntryDetailRead(EntryRead):
    links: list[LinkRead] = Field(default_factory=list)


class EntryListResponse(BaseModel):
    items: list[EntryRead]
    total: int
    limit: int
    offset: int


class GroupNode(BaseModel):
    id: str
    name: str
    kind: EntryKind
    amount_minor: int
    occurred_at: date


class GroupEdge(BaseModel):
    id: str
    source_entry_id: str
    target_entry_id: str
    link_type: LinkType
    note: str | None = None


class GroupGraphRead(BaseModel):
    group_id: str
    nodes: list[GroupNode]
    edges: list[GroupEdge]


class GroupSummaryRead(BaseModel):
    group_id: str
    entry_count: int
    edge_count: int
    first_occurred_at: date
    last_occurred_at: date
    latest_entry_name: str


class DailyExpensePoint(BaseModel):
    date: date
    currency_code: str
    total_minor: int


class TagBreakdownItem(BaseModel):
    tag: str
    currency_code: str
    total_minor: int


class DashboardKpisRead(BaseModel):
    expense_total_minor: int
    income_total_minor: int
    net_total_minor: int
    daily_expense_total_minor: int
    non_daily_expense_total_minor: int
    average_daily_expense_minor: int
    median_daily_expense_minor: int
    daily_spending_days: int


class DashboardDailySpendingPoint(BaseModel):
    date: date
    expense_total_minor: int
    daily_expense_minor: int
    non_daily_expense_minor: int


class DashboardMonthlyTrendPoint(BaseModel):
    month: str
    expense_total_minor: int
    income_total_minor: int
    daily_expense_minor: int
    non_daily_expense_minor: int


class DashboardBreakdownItem(BaseModel):
    label: str
    total_minor: int
    share: float


class DashboardWeekdaySpendingPoint(BaseModel):
    weekday: str
    total_minor: int


class DashboardLargestExpenseItem(BaseModel):
    id: str
    occurred_at: date
    name: str
    to_entity: str | None = None
    amount_minor: int
    is_daily: bool


class DashboardProjectionRead(BaseModel):
    is_current_month: bool
    days_elapsed: int
    days_remaining: int
    spent_to_date_minor: int
    projected_total_minor: int | None = None
    projected_remaining_minor: int | None = None


class DashboardRead(BaseModel):
    month: str
    currency_code: str
    kpis: DashboardKpisRead
    daily_spending: list[DashboardDailySpendingPoint]
    monthly_trend: list[DashboardMonthlyTrendPoint]
    spending_by_from: list[DashboardBreakdownItem]
    spending_by_to: list[DashboardBreakdownItem]
    spending_by_tag: list[DashboardBreakdownItem]
    weekday_spending: list[DashboardWeekdaySpendingPoint]
    largest_expenses: list[DashboardLargestExpenseItem]
    projection: DashboardProjectionRead
    reconciliation: list[ReconciliationRead]


class RuntimeSettingsOverridesRead(BaseModel):
    current_user_name: str | None = None
    user_memory: str | None = None
    default_currency_code: str | None = None
    dashboard_currency_code: str | None = None
    agent_model: str | None = None
    agent_max_steps: int | None = None
    agent_retry_max_attempts: int | None = None
    agent_retry_initial_wait_seconds: float | None = None
    agent_retry_max_wait_seconds: float | None = None
    agent_retry_backoff_multiplier: float | None = None
    agent_max_image_size_bytes: int | None = None
    agent_max_images_per_message: int | None = None
    agent_base_url: str | None = None
    agent_api_key_configured: bool = False


class RuntimeSettingsRead(BaseModel):
    current_user_name: str
    user_memory: str | None = None
    default_currency_code: str
    dashboard_currency_code: str
    agent_model: str
    agent_max_steps: int
    agent_retry_max_attempts: int
    agent_retry_initial_wait_seconds: float
    agent_retry_max_wait_seconds: float
    agent_retry_backoff_multiplier: float
    agent_max_image_size_bytes: int
    agent_max_images_per_message: int
    agent_base_url: str | None = None
    agent_api_key_configured: bool = False
    overrides: RuntimeSettingsOverridesRead


class RuntimeSettingsUpdate(BaseModel):
    current_user_name: str | None = Field(default=None, max_length=255)
    user_memory: str | None = Field(default=None, max_length=4000)
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    dashboard_currency_code: str | None = Field(
        default=None, min_length=3, max_length=3
    )
    agent_model: str | None = Field(default=None, max_length=255)
    agent_max_steps: int | None = Field(default=None, ge=1, le=500)
    agent_retry_max_attempts: int | None = Field(default=None, ge=1, le=10)
    agent_retry_initial_wait_seconds: float | None = Field(
        default=None, ge=0.0, le=30.0
    )
    agent_retry_max_wait_seconds: float | None = Field(default=None, ge=0.0, le=120.0)
    agent_retry_backoff_multiplier: float | None = Field(default=None, ge=1.0, le=10.0)
    agent_max_image_size_bytes: int | None = Field(default=None, ge=1024, le=104857600)
    agent_max_images_per_message: int | None = Field(default=None, ge=1, le=12)
    agent_base_url: str | None = Field(default=None, max_length=500)
    agent_api_key: str | None = Field(default=None, max_length=500)

    @field_validator(
        "current_user_name",
        "agent_model",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip()
        return normalized or None

    @field_validator("user_memory", mode="before")
    @classmethod
    def normalize_optional_multiline_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).replace("\r\n", "\n").replace("\r", "\n")
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()
        return normalized or None

    @field_validator("default_currency_code", "dashboard_currency_code", mode="before")
    @classmethod
    def normalize_optional_currency(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip().upper()
        return normalized or None

    @field_validator("agent_base_url", mode="before")
    @classmethod
    def validate_agent_base_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = " ".join(str(value).split()).strip()
        if not normalized:
            return None
        # Validate URL format
        parsed = urlparse(normalized)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("agent_base_url must use http or https scheme")
        if not parsed.netloc:
            raise ValueError("agent_base_url must have a valid host")
        hostname = (parsed.hostname or "").strip().lower()
        if not hostname:
            raise ValueError("agent_base_url must have a valid host")
        if hostname == "localhost" or hostname.endswith(".localhost"):
            raise ValueError("agent_base_url cannot point to localhost hosts")

        # Block unsafe IP literals to reduce SSRF risk.
        try:
            host_ip = ip_address(hostname)
        except ValueError:
            return normalized
        if (
            host_ip.is_private
            or host_ip.is_loopback
            or host_ip.is_link_local
            or host_ip.is_reserved
            or host_ip.is_multicast
            or host_ip.is_unspecified
        ):
            raise ValueError("agent_base_url cannot point to non-public IP addresses")
        return normalized

    @field_validator("agent_api_key", mode="before")
    @classmethod
    def validate_agent_api_key(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            return None
        # Reject masked sentinel to prevent accidental overwrites
        if normalized == "***masked***":
            raise ValueError("agent_api_key cannot be the masked sentinel value")
        return normalized


class AgentThreadCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class AgentThreadRead(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentThreadSummaryRead(AgentThreadRead):
    last_message_preview: str | None = None
    pending_change_count: int = 0


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
    input_json: dict[str, Any]
    output_json: dict[str, Any]
    output_text: str
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
    status: AgentRunStatus
    model_name: str
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
