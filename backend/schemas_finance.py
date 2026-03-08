from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.enums_finance import EntryKind, LinkType
from backend.services.runtime_settings_normalization import (
    normalize_currency_code_or_none,
    normalize_text_or_none,
    normalize_user_memory_items_or_none,
    validate_user_memory_size,
    validate_agent_api_key_or_none,
    validate_agent_base_url_or_none,
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
    is_account: bool = False
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
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class TaxonomyTermUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class TaxonomyTermRead(BaseModel):
    id: str
    taxonomy_id: str
    name: str
    normalized_name: str
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
    from_entity_missing: bool = False
    to_entity: str | None = None
    to_entity_missing: bool = False
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
    user_memory: list[str] | None = None
    default_currency_code: str | None = None
    dashboard_currency_code: str | None = None
    agent_model: str | None = None
    agent_max_steps: int | None = None
    agent_bulk_max_concurrent_threads: int | None = None
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
    user_memory: list[str] | None = None
    default_currency_code: str
    dashboard_currency_code: str
    agent_model: str
    agent_max_steps: int
    agent_bulk_max_concurrent_threads: int
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
    model_config = ConfigDict(extra="forbid")

    user_memory: list[str] | None = None
    default_currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    dashboard_currency_code: str | None = Field(
        default=None, min_length=3, max_length=3
    )
    agent_model: str | None = Field(default=None, max_length=255)
    agent_max_steps: int | None = Field(default=None, ge=1, le=500)
    agent_bulk_max_concurrent_threads: int | None = Field(default=None, ge=1, le=16)
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
        "agent_model",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_text_or_none(str(value))

    @field_validator("user_memory", mode="before")
    @classmethod
    def normalize_optional_user_memory(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            raise ValueError("user_memory must be a list of strings")
        if not isinstance(value, list):
            raise ValueError("user_memory must be a list of strings")
        return validate_user_memory_size(
            normalize_user_memory_items_or_none(str(item) for item in value)
        )

    @field_validator("default_currency_code", "dashboard_currency_code", mode="before")
    @classmethod
    def normalize_optional_currency(cls, value: Any) -> str | None:
        if value is None:
            return None
        return normalize_currency_code_or_none(str(value))

    @field_validator("agent_base_url", mode="before")
    @classmethod
    def validate_agent_base_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        return validate_agent_base_url_or_none(str(value))

    @field_validator("agent_api_key", mode="before")
    @classmethod
    def validate_agent_api_key(cls, value: Any) -> str | None:
        if value is None:
            return None
        return validate_agent_api_key_or_none(str(value))
