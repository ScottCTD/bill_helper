from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.contracts_groups import GroupCreateCommand, GroupMemberCreateCommand, GroupPatch
from backend.contracts_users import UserCreateCommand, UserPatch
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
from backend.validation.contract_fields import NonEmptyPatchModel


class TagSummaryRead(BaseModel):
    id: int
    name: str
    color: str | None = None
    description: str | None = None
    type: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TagRead(TagSummaryRead):
    entry_count: int



class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    type: str | None = Field(default=None, max_length=100)


class TagUpdate(NonEmptyPatchModel):
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
    net_amount_minor: int | None = None
    net_amount_currency_code: str | None = None
    net_amount_mixed_currencies: bool = False

    model_config = ConfigDict(from_attributes=True)


class EntityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)


class EntityUpdate(NonEmptyPatchModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)


class UserRead(BaseModel):
    id: str
    name: str
    is_admin: bool = False
    is_current_user: bool = False
    account_count: int | None = None
    entry_count: int | None = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(UserCreateCommand):
    pass


class UserUpdate(UserPatch):
    pass


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


class AccountUpdate(NonEmptyPatchModel):
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
    direct_group_id: str | None = None
    direct_group_member_role: GroupMemberRole | None = None

    @model_validator(mode="after")
    def validate_direct_group_membership(self) -> EntryCreate:
        if self.direct_group_id is None and self.direct_group_member_role is not None:
            raise ValueError("direct_group_member_role requires direct_group_id.")
        return self


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
    direct_group_id: str | None = None
    direct_group_member_role: GroupMemberRole | None = None


class EntryRead(BaseModel):
    id: str
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
    tags: list[TagSummaryRead] = Field(default_factory=list)
    direct_group: EntryGroupRefRead | None = None
    direct_group_member_role: GroupMemberRole | None = None
    group_path: list[EntryGroupRefRead] = Field(default_factory=list)


class EntryDetailRead(EntryRead):
    pass


class EntryListResponse(BaseModel):
    items: list[EntryRead]
    total: int
    limit: int
    offset: int


class EntryGroupRefRead(BaseModel):
    id: str
    name: str
    group_type: GroupType


class GroupCreate(GroupCreateCommand):
    pass


class GroupUpdate(GroupPatch):
    pass


class GroupMemberCreate(GroupMemberCreateCommand):
    pass


class GroupNode(BaseModel):
    graph_id: str
    membership_id: str
    subject_id: str
    node_type: Literal["ENTRY", "GROUP"]
    name: str
    member_role: GroupMemberRole | None = None
    representative_occurred_at: date | None = None
    kind: EntryKind | None = None
    amount_minor: int | None = None
    currency_code: str | None = None
    occurred_at: date | None = None
    group_type: GroupType | None = None
    descendant_entry_count: int | None = None
    first_occurred_at: date | None = None
    last_occurred_at: date | None = None


class GroupEdge(BaseModel):
    id: str
    source_graph_id: str
    target_graph_id: str
    group_type: GroupType


class GroupGraphRead(BaseModel):
    id: str
    name: str
    group_type: GroupType
    parent_group_id: str | None = None
    direct_member_count: int
    direct_entry_count: int
    direct_child_group_count: int
    descendant_entry_count: int
    first_occurred_at: date | None = None
    last_occurred_at: date | None = None
    nodes: list[GroupNode]
    edges: list[GroupEdge]


class GroupSummaryRead(BaseModel):
    id: str
    name: str
    group_type: GroupType
    parent_group_id: str | None = None
    direct_member_count: int
    direct_entry_count: int
    direct_child_group_count: int
    descendant_entry_count: int
    first_occurred_at: date | None = None
    last_occurred_at: date | None = None


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
