from __future__ import annotations

from datetime import date as DateValue
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.enums_finance import EntryKind
from backend.services.agent.change_contracts.common import (
    normalize_object_json_string,
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


def _is_complete_entry_selector_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("date") is None or value.get("amount_minor") is None:
        return False
    return all(
        normalize_optional_reference_id(value.get(field)) is not None
        for field in ("from_entity", "to_entity", "name")
    )


def normalize_entry_reference_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    if "entry_id" in normalized:
        normalized["entry_id"] = normalize_optional_reference_id(normalized.get("entry_id"))
    selector = normalize_object_json_string(normalized.get("selector"))
    if normalized.get("entry_id") is not None and not _is_complete_entry_selector_payload(selector):
        normalized["selector"] = None
    else:
        normalized["selector"] = selector
    return normalized


class CreateEntryPayload(BaseModel):
    kind: EntryKind
    date: DateValue
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    from_entity: RequiredEntityName = Field(min_length=1, max_length=255)
    to_entity: RequiredEntityName = Field(min_length=1, max_length=255)
    tags: NormalizedTagList = Field(default_factory=list)
    markdown_notes: str | None = None


class EntrySelectorPayload(BaseModel):
    date: DateValue
    amount_minor: int = Field(gt=0)
    from_entity: RequiredEntityName = Field(min_length=1, max_length=255)
    to_entity: RequiredEntityName = Field(min_length=1, max_length=255)
    name: RequiredEntityName = Field(min_length=1, max_length=255)


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


class UpdateEntryPayload(BaseModel):
    entry_id: str | None = Field(default=None, min_length=4, max_length=36)
    selector: EntrySelectorPayload | None = None
    patch: UpdateEntryPatchPayload

    @field_validator("entry_id")
    @classmethod
    def normalize_entry_id(cls, value: str | None) -> str | None:
        return normalize_optional_reference_id(value)

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        normalized = normalize_entry_reference_payload(value)
        if not isinstance(normalized, dict):
            return normalized
        normalized["patch"] = normalize_object_json_string(normalized.get("patch"))
        return normalized

    @model_validator(mode="after")
    def ensure_reference_present(self) -> UpdateEntryPayload:
        if self.entry_id is None and self.selector is None:
            raise ValueError("either entry_id or selector is required")
        return self


class DeleteEntryPayload(BaseModel):
    entry_id: str | None = Field(default=None, min_length=4, max_length=36)
    selector: EntrySelectorPayload | None = None

    @field_validator("entry_id")
    @classmethod
    def normalize_entry_id(cls, value: str | None) -> str | None:
        return normalize_optional_reference_id(value)

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        return normalize_entry_reference_payload(value)

    @model_validator(mode="after")
    def ensure_reference_present(self) -> DeleteEntryPayload:
        if self.entry_id is None and self.selector is None:
            raise ValueError("either entry_id or selector is required")
        return self


class EntryReferencePayload(BaseModel):
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
