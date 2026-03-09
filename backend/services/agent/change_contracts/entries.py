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
from backend.services.agent.payload_normalization import normalize_required_text
from backend.validation.finance_names import normalize_tag_name


def normalize_entry_reference_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    if "entry_id" in normalized:
        normalized["entry_id"] = normalize_optional_reference_id(normalized.get("entry_id"))
    normalized["selector"] = normalize_object_json_string(normalized.get("selector"))
    return normalized


class CreateEntryPayload(BaseModel):
    kind: EntryKind
    date: DateValue
    name: str = Field(min_length=1, max_length=255)
    amount_minor: int = Field(gt=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    from_entity: str = Field(min_length=1, max_length=255)
    to_entity: str = Field(min_length=1, max_length=255)
    tags: list[str] = Field(default_factory=list)
    markdown_notes: str | None = None

    @field_validator("name", "from_entity", "to_entity")
    @classmethod
    def normalize_required_fields(cls, value: str) -> str:
        return normalize_required_text(value)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})


class EntrySelectorPayload(BaseModel):
    date: DateValue
    amount_minor: int = Field(gt=0)
    from_entity: str = Field(min_length=1, max_length=255)
    to_entity: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)

    @field_validator("from_entity", "to_entity", "name")
    @classmethod
    def normalize_selector_text(cls, value: str) -> str:
        return normalize_required_text(value)


class UpdateEntryPatchPayload(BaseModel):
    kind: EntryKind | None = None
    date: DateValue | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    amount_minor: int | None = Field(default=None, gt=0)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    from_entity: str | None = Field(default=None, min_length=1, max_length=255)
    to_entity: str | None = Field(default=None, min_length=1, max_length=255)
    tags: list[str] | None = None
    markdown_notes: str | None = None

    @field_validator("name", "from_entity", "to_entity")
    @classmethod
    def normalize_optional_text_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @field_validator("currency_code")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return sorted({normalize_tag_name(tag) for tag in value if tag.strip()})

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateEntryPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


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
