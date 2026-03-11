from __future__ import annotations

from datetime import date as DateValue
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.enums_agent import AgentChangeStatus
from backend.enums_finance import GroupType
from backend.services.agent.payload_normalization import normalize_loose_text, normalize_required_text
from backend.validation.contract_fields import (
    NormalizedTagList,
    OptionalCategory,
    OptionalCurrencyCode,
    OptionalLooseText,
    QueryEntityName,
    QueryTagName,
)


_DATE_DESC = "ISO date YYYY-MM-DD, e.g. '2026-03-02'"


class ListEntriesArgs(BaseModel):
    date: DateValue | None = Field(default=None, description=_DATE_DESC)
    start_date: DateValue | None = Field(
        default=None,
        description=(
            f"{_DATE_DESC}. When both start_date and end_date are set, "
            "end_date must be >= start_date."
        ),
    )
    end_date: DateValue | None = Field(default=None, description=_DATE_DESC)
    source: OptionalLooseText = None
    name: OptionalLooseText = None
    from_entity: OptionalLooseText = None
    to_entity: OptionalLooseText = None
    tags: NormalizedTagList = Field(default_factory=list)
    kind: str | None = Field(default=None, pattern="^(EXPENSE|INCOME|TRANSFER)$")
    limit: int = Field(
        default=10,
        ge=1,
        description="Max entries to return. No upper bound; be cautious with very large values.",
    )

    @model_validator(mode="after")
    def validate_date_window(self) -> ListEntriesArgs:
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date cannot be greater than end_date")
        return self


class ListTagsArgs(BaseModel):
    name: QueryTagName = None
    type: OptionalCategory = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max tags to return. No upper bound; be cautious with very large values.",
    )


class ListEntitiesArgs(BaseModel):
    name: QueryEntityName = None
    category: OptionalCategory = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max entities to return. No upper bound; be cautious with very large values.",
    )


class ListAccountsArgs(BaseModel):
    name: QueryEntityName = None
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max accounts to return. No upper bound; be cautious with very large values.",
    )


class ListSnapshotsArgs(BaseModel):
    account_id: str = Field(
        min_length=4,
        max_length=36,
        description="Existing account id from list_accounts.",
    )
    limit: int = Field(
        default=20,
        ge=1,
        description="Max snapshots to return. No upper bound; be cautious with very large values.",
    )


class GetReconciliationArgs(BaseModel):
    account_id: str = Field(
        min_length=4,
        max_length=36,
        description="Existing account id from list_accounts.",
    )
    as_of: DateValue | None = Field(default=None, description=_DATE_DESC)


class ListGroupsArgs(BaseModel):
    group_id: str | None = Field(
        default=None,
        min_length=4,
        max_length=36,
        description=(
            "Optional full group id or unique short-id prefix to inspect one group in detail. "
            "When provided, do not also send name/group_type/limit."
        ),
    )
    name: str | None = None
    group_type: GroupType | None = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max groups to return in list mode. No upper bound; be cautious with very large values.",
    )

    @field_validator("group_id")
    @classmethod
    def normalize_group_id(cls, value: str | None) -> str | None:
        normalized = normalize_loose_text(value)
        return normalized.lower() if normalized is not None else None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        return normalize_loose_text(value)

    @model_validator(mode="after")
    def validate_mode(self) -> ListGroupsArgs:
        if self.group_id is not None and (
            self.name is not None or self.group_type is not None or self.limit != 10
        ):
            raise ValueError("group_id cannot be combined with name, group_type, or limit")
        return self


ProposalType = Literal["entry", "tag", "entity", "account", "snapshot", "group"]
ProposalAction = Literal["create", "update", "delete"]


class ListProposalsArgs(BaseModel):
    proposal_type: ProposalType | None = Field(
        default=None,
        description="Filter by proposal domain: entry, account, snapshot, group, tag, or entity.",
    )
    proposal_status: AgentChangeStatus | None = Field(
        default=None,
        description=(
            "Filter by lifecycle status. Supported values: PENDING_REVIEW, APPROVED, "
            "REJECTED, APPLIED, APPLY_FAILED."
        ),
    )
    change_action: ProposalAction | None = Field(
        default=None,
        description="Filter by CRUD action: create, update, or delete.",
    )
    proposal_id: str | None = Field(
        default=None,
        min_length=4,
        max_length=36,
        description="Optional full proposal id or unique short-id prefix to inspect one proposal.",
    )
    limit: int = Field(
        default=10,
        ge=1,
        description="Max proposals to return. No upper bound; be cautious with very large values.",
    )

    @field_validator("proposal_type", mode="before")
    @classmethod
    def normalize_proposal_type(cls, value: object) -> object:
        if value is None:
            return None
        return normalize_required_text(str(value)).lower()

    @field_validator("proposal_status", mode="before")
    @classmethod
    def normalize_proposal_status(cls, value: object) -> object:
        if value is None or isinstance(value, AgentChangeStatus):
            return value
        normalized = normalize_required_text(str(value)).upper().replace("-", "_").replace(" ", "_")
        aliases = {
            "PENDING": AgentChangeStatus.PENDING_REVIEW.value,
            "FAILED": AgentChangeStatus.APPLY_FAILED.value,
        }
        return aliases.get(normalized, normalized)

    @field_validator("change_action", mode="before")
    @classmethod
    def normalize_change_action(cls, value: object) -> object:
        if value is None:
            return None
        return normalize_required_text(str(value)).lower()

    @field_validator("proposal_id")
    @classmethod
    def normalize_proposal_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_required_text(value)
        return normalized.lower()
