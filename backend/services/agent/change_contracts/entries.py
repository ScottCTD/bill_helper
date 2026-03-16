# CALLING SPEC:
# - Purpose: implement focused service logic for `entries`.
# - Inputs: callers that import `backend/services/agent/change_contracts/entries.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `entries`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from datetime import date as DateValue
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.enums_finance import EntryKind
from backend.services.agent.change_contracts.common import (
    normalize_optional_proposal_id,
    normalize_optional_reference_id,
)
from backend.validation.contract_fields import (
    NonEmptyPatchModel,
    NormalizedTagList,
    OptionalCurrencyCode,
    OptionalEntityName,
    RequiredEntityName,
)


class ChangePayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateEntryPayload(ChangePayloadModel):
    kind: EntryKind
    date: DateValue
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    from_entity: RequiredEntityName = Field(min_length=1, max_length=255)
    to_entity: RequiredEntityName = Field(min_length=1, max_length=255)
    tags: NormalizedTagList = Field(default_factory=list)
    markdown_notes: str | None = None


class UpdateEntryPatchPayload(NonEmptyPatchModel):
    kind: EntryKind | None = None
    date: DateValue | None = None
    name: OptionalEntityName = Field(default=None, min_length=1, max_length=255)
    amount_minor: int | None = Field(default=None, gt=0)
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    from_entity: OptionalEntityName = Field(default=None, min_length=1, max_length=255)
    to_entity: OptionalEntityName = Field(default=None, min_length=1, max_length=255)
    tags: NormalizedTagList | None = None
    markdown_notes: str | None = None


class UpdateEntryPayload(ChangePayloadModel):
    entry_id: str = Field(min_length=4, max_length=36)
    patch: UpdateEntryPatchPayload
    target: dict[str, Any] | None = None

    @field_validator("entry_id")
    @classmethod
    def normalize_entry_id(cls, value: str) -> str:
        normalized = normalize_optional_reference_id(value)
        if normalized is None:
            raise ValueError("entry_id is required")
        return normalized


class DeleteEntryPayload(ChangePayloadModel):
    entry_id: str = Field(min_length=4, max_length=36)
    target: dict[str, Any] | None = None

    @field_validator("entry_id")
    @classmethod
    def normalize_entry_id(cls, value: str) -> str:
        normalized = normalize_optional_reference_id(value)
        if normalized is None:
            raise ValueError("entry_id is required")
        return normalized


class EntryReferencePayload(ChangePayloadModel):
    entry_id: str | None = Field(default=None, min_length=4, max_length=36)
    create_entry_proposal_id: str | None = Field(default=None, min_length=4, max_length=36)

    @field_validator("entry_id")
    @classmethod
    def normalize_entry_id(cls, value: str | None) -> str | None:
        return normalize_optional_reference_id(value)

    @field_validator("create_entry_proposal_id")
    @classmethod
    def normalize_create_entry_proposal_id(cls, value: str | None) -> str | None:
        return normalize_optional_proposal_id(value)

    @model_validator(mode="after")
    def ensure_reference_present(self) -> EntryReferencePayload:
        if (self.entry_id is None) == (self.create_entry_proposal_id is None):
            raise ValueError("exactly one of entry_id or create_entry_proposal_id is required")
        return self
