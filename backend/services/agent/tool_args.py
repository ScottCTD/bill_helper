from __future__ import annotations

from datetime import date as DateValue
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.enums_agent import AgentChangeStatus
from backend.enums_finance import GroupMemberRole, GroupType
from backend.services.agent.threads import THREAD_TITLE_MAX_LENGTH, validate_thread_title
from backend.services.agent.payload_normalization import (
    normalize_loose_text,
    normalize_optional_category,
    normalize_required_text,
)
from backend.services.runtime_settings_normalization import (
    normalize_user_memory_items_or_none,
    validate_user_memory_size,
)
from backend.services.agent.change_contracts import (
    CreateAccountPayload as ProposeCreateAccountArgs,
    CreateEntityPayload as ProposeCreateEntityArgs,
    CreateEntryPayload as ProposeCreateEntryArgs,
    CreateGroupPayload as ProposeCreateGroupArgs,
    CreateTagPayload as ProposeCreateTagArgs,
    DeleteAccountPayload as ProposeDeleteAccountArgs,
    DeleteEntityPayload as ProposeDeleteEntityArgs,
    DeleteEntryPayload as ProposeDeleteEntryArgs,
    DeleteGroupPayload as ProposeDeleteGroupArgs,
    DeleteTagPayload as ProposeDeleteTagArgs,
    UpdateAccountPatchPayload as AccountPatchArgs,
    UpdateAccountPayload as ProposeUpdateAccountArgs,
    EntryReferencePayload,
    EntrySelectorPayload as EntrySelectorArgs,
    GroupReferencePayload,
    normalize_object_json_string,
    UpdateEntityPatchPayload as EntityPatchArgs,
    UpdateEntityPayload as ProposeUpdateEntityArgs,
    UpdateEntryPatchPayload as EntryPatchArgs,
    UpdateEntryPayload as ProposeUpdateEntryArgs,
    UpdateGroupPatchPayload as GroupPatchArgs,
    UpdateGroupPayload as ProposeUpdateGroupArgs,
    UpdateTagPatchPayload as TagPatchArgs,
    UpdateTagPayload as ProposeUpdateTagArgs,
)
from backend.services.entries import normalize_tag_name
from backend.services.entities import normalize_entity_name


INTERMEDIATE_UPDATE_TOOL_NAME = "send_intermediate_update"


class EmptyArgs(BaseModel):
    pass


class SendIntermediateUpdateArgs(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=400,
        description=(
            "A short, user-visible progress note. Use plain text or inline markdown "
            "(e.g. **bold**, `code`, *italic*) for emphasis when helpful."
        ),
    )

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized


class AddUserMemoryArgs(BaseModel):
    memory_items: list[str] = Field(
        min_length=1,
        max_length=20,
        description=(
            "New persistent memory items to append. Each item should be a short standalone "
            "user preference, rule, or hint."
        ),
    )

    @field_validator("memory_items")
    @classmethod
    def normalize_memory_items(cls, value: list[str]) -> list[str]:
        normalized = validate_user_memory_size(normalize_user_memory_items_or_none(value))
        if normalized is None:
            raise ValueError("memory_items must include at least one non-empty item")
        return normalized


class RenameThreadArgs(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=THREAD_TITLE_MAX_LENGTH,
        description="Short thread title/topic in 1-5 words.",
    )

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return validate_thread_title(value)


_DATE_DESC = "ISO date YYYY-MM-DD, e.g. '2026-03-02'"


class ListEntriesArgs(BaseModel):
    date: DateValue | None = Field(default=None, description=_DATE_DESC)
    start_date: DateValue | None = Field(default=None, description=f"{_DATE_DESC}. When both start_date and end_date are set, end_date must be >= start_date.")
    end_date: DateValue | None = Field(default=None, description=_DATE_DESC)
    source: str | None = None
    name: str | None = None
    from_entity: str | None = None
    to_entity: str | None = None
    tags: list[str] = Field(default_factory=list)
    kind: str | None = Field(default=None, pattern="^(EXPENSE|INCOME|TRANSFER)$")
    limit: int = Field(
        default=10,
        ge=1,
        description="Max entries to return. No upper bound; be cautious with very large values.",
    )

    @field_validator("source", "name", "from_entity", "to_entity")
    @classmethod
    def normalize_query_text(cls, value: str | None) -> str | None:
        return normalize_loose_text(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})

    @model_validator(mode="after")
    def validate_date_window(self) -> ListEntriesArgs:
        if self.start_date is not None and self.end_date is not None and self.start_date > self.end_date:
            raise ValueError("start_date cannot be greater than end_date")
        return self


class ListTagsArgs(BaseModel):
    name: str | None = None
    type: str | None = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max tags to return. No upper bound; be cautious with very large values.",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        normalized = normalize_loose_text(value)
        return normalize_tag_name(normalized) if normalized is not None else None

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str | None) -> str | None:
        return normalize_optional_category(value)


class ListEntitiesArgs(BaseModel):
    name: str | None = None
    category: str | None = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max entities to return. No upper bound; be cautious with very large values.",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        normalized = normalize_loose_text(value)
        return normalize_entity_name(normalized) if normalized is not None else None

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return normalize_optional_category(value)


class ListAccountsArgs(BaseModel):
    name: str | None = None
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
    limit: int = Field(
        default=10,
        ge=1,
        description="Max accounts to return. No upper bound; be cautious with very large values.",
    )

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        normalized = normalize_loose_text(value)
        return normalize_entity_name(normalized) if normalized is not None else None

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value).upper()


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


ProposalType = Literal["entry", "tag", "entity", "account", "group"]
ProposalAction = Literal["create", "update", "delete"]


class ListProposalsArgs(BaseModel):
    proposal_type: ProposalType | None = Field(
        default=None,
        description="Filter by proposal domain: entry, account, group, tag, or entity.",
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


class UpdatePendingProposalArgs(BaseModel):
    proposal_id: str = Field(min_length=4, max_length=36)
    patch_map: dict[str, object]

    @field_validator("proposal_id")
    @classmethod
    def normalize_proposal_id(cls, value: str) -> str:
        normalized = normalize_required_text(value)
        return normalized.lower()

    @field_validator("patch_map")
    @classmethod
    def normalize_patch_map(cls, value: dict[str, object]) -> dict[str, object]:
        normalized: dict[str, object] = {}
        for raw_key, raw_value in value.items():
            key = normalize_required_text(str(raw_key))
            normalized[key] = raw_value
        if not normalized:
            raise ValueError("patch_map must include at least one field")
        return normalized


class RemovePendingProposalArgs(BaseModel):
    proposal_id: str = Field(min_length=4, max_length=36)

    @field_validator("proposal_id")
    @classmethod
    def normalize_proposal_id(cls, value: str) -> str:
        normalized = normalize_required_text(value)
        return normalized.lower()


class ProposeUpdateGroupMembershipArgs(BaseModel):
    action: Literal["add", "remove"]
    group_ref: GroupReferencePayload
    entry_ref: EntryReferencePayload | None = None
    child_group_ref: GroupReferencePayload | None = None
    member_role: GroupMemberRole | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["group_ref"] = normalize_object_json_string(normalized.get("group_ref"))
        normalized["entry_ref"] = normalize_object_json_string(normalized.get("entry_ref"))
        normalized["child_group_ref"] = normalize_object_json_string(normalized.get("child_group_ref"))
        return normalized

    @model_validator(mode="after")
    def validate_targets(self) -> ProposeUpdateGroupMembershipArgs:
        if (self.entry_ref is None) == (self.child_group_ref is None):
            raise ValueError("exactly one of entry_ref or child_group_ref is required")
        if self.action == "remove":
            if self.member_role is not None:
                raise ValueError("member_role is only valid for add action")
            if self.group_ref.create_group_proposal_id is not None:
                raise ValueError("remove action only supports existing group_id references")
            if self.entry_ref is not None and self.entry_ref.create_entry_proposal_id is not None:
                raise ValueError("remove action only supports existing entry_id references")
            if self.child_group_ref is not None and self.child_group_ref.create_group_proposal_id is not None:
                raise ValueError("remove action only supports existing child group_id references")
        return self
