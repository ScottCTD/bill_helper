from __future__ import annotations

from datetime import date as DateValue

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.services.agent.change_contracts import (
    CreateEntityPayload as ProposeCreateEntityArgs,
    CreateEntryPayload as ProposeCreateEntryArgs,
    CreateTagPayload as ProposeCreateTagArgs,
    DeleteEntityPayload as ProposeDeleteEntityArgs,
    DeleteEntryPayload as ProposeDeleteEntryArgs,
    DeleteTagPayload as ProposeDeleteTagArgs,
    EntrySelectorPayload as EntrySelectorArgs,
    UpdateEntityPatchPayload as EntityPatchArgs,
    UpdateEntityPayload as ProposeUpdateEntityArgs,
    UpdateEntryPatchPayload as EntryPatchArgs,
    UpdateEntryPayload as ProposeUpdateEntryArgs,
    UpdateTagPatchPayload as TagPatchArgs,
    UpdateTagPayload as ProposeUpdateTagArgs,
)
from backend.services.entries import normalize_tag_name
from backend.services.entities import normalize_entity_category, normalize_entity_name


INTERMEDIATE_UPDATE_TOOL_NAME = "send_intermediate_update"


def normalize_loose_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def normalize_required_text(value: str) -> str:
    normalized = normalize_loose_text(value)
    if normalized is None:
        raise ValueError("value cannot be empty")
    return normalized


def normalize_optional_category(value: str | None) -> str | None:
    return normalize_entity_category(value)


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


_DATE_DESC = "ISO date YYYY-MM-DD, e.g. '2026-03-02'"


class ListEntriesArgs(BaseModel):
    date: DateValue | None = Field(default=None, description=_DATE_DESC)
    start_date: DateValue | None = Field(default=None, description=f"{_DATE_DESC}. When both start_date and end_date are set, end_date must be >= start_date.")
    end_date: DateValue | None = Field(default=None, description=_DATE_DESC)
    name: str | None = None
    from_entity: str | None = None
    to_entity: str | None = None
    tags: list[str] = Field(default_factory=list)
    kind: str | None = Field(default=None, pattern="^(EXPENSE|INCOME|TRANSFER)$")
    limit: int = Field(
        default=50,
        ge=1,
        description="Max entries to return. No upper bound; be cautious with very large values.",
    )

    @field_validator("name", "from_entity", "to_entity")
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
        default=50,
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
        default=200,
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

