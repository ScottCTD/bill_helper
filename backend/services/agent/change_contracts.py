from __future__ import annotations

from datetime import date as DateValue
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.enums_agent import AgentChangeType
from backend.enums_finance import EntryKind
from backend.services.entries import normalize_tag_name
from backend.services.entities import normalize_entity_category, normalize_entity_name


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


def normalize_object_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    candidate = value.strip()
    if not candidate or not (candidate.startswith("{") and candidate.endswith("}")):
        return value
    try:
        import json

        decoded = json.loads(candidate)
    except (TypeError, ValueError):
        return value
    return decoded if isinstance(decoded, dict) else value


class CreateTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    type: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str) -> str:
        normalized = normalize_optional_category(value)
        if normalized is None:
            raise ValueError("type cannot be empty")
        return normalized


class UpdateTagPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    type: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("type")
    @classmethod
    def normalize_type(cls, value: str | None) -> str | None:
        return normalize_optional_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateTagPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    patch: UpdateTagPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class DeleteTagPayload(BaseModel):
    name: str = Field(min_length=1, max_length=64)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_tag_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class CreateEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str) -> str:
        normalized = normalize_optional_category(value)
        if normalized is None:
            raise ValueError("category cannot be empty")
        return normalized


class UpdateEntityPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("category")
    @classmethod
    def normalize_category(cls, value: str | None) -> str | None:
        return normalize_optional_category(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateEntityPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    patch: UpdateEntityPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class DeleteEntityPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
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
    selector: EntrySelectorPayload
    patch: UpdateEntryPatchPayload

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["selector"] = normalize_object_json_string(normalized.get("selector"))
        normalized["patch"] = normalize_object_json_string(normalized.get("patch"))
        return normalized


class DeleteEntryPayload(BaseModel):
    selector: EntrySelectorPayload

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["selector"] = normalize_object_json_string(normalized.get("selector"))
        return normalized


CHANGE_PAYLOAD_MODELS: dict[AgentChangeType, type[BaseModel]] = {
    AgentChangeType.CREATE_TAG: CreateTagPayload,
    AgentChangeType.UPDATE_TAG: UpdateTagPayload,
    AgentChangeType.DELETE_TAG: DeleteTagPayload,
    AgentChangeType.CREATE_ENTITY: CreateEntityPayload,
    AgentChangeType.UPDATE_ENTITY: UpdateEntityPayload,
    AgentChangeType.DELETE_ENTITY: DeleteEntityPayload,
    AgentChangeType.CREATE_ENTRY: CreateEntryPayload,
    AgentChangeType.UPDATE_ENTRY: UpdateEntryPayload,
    AgentChangeType.DELETE_ENTRY: DeleteEntryPayload,
}


def validate_change_payload(change_type: AgentChangeType, payload: dict[str, Any]) -> BaseModel:
    model_type = CHANGE_PAYLOAD_MODELS.get(change_type)
    if model_type is None:  # pragma: no cover - enum guard
        raise ValueError(f"unsupported proposal change type: {change_type.value}")
    return model_type.model_validate(payload)


PROPOSAL_MUTABLE_ROOTS: dict[AgentChangeType, set[str]] = {
    AgentChangeType.CREATE_TAG: {"name", "type"},
    AgentChangeType.UPDATE_TAG: {"name", "patch"},
    AgentChangeType.DELETE_TAG: {"name"},
    AgentChangeType.CREATE_ENTITY: {"name", "category"},
    AgentChangeType.UPDATE_ENTITY: {"name", "patch"},
    AgentChangeType.DELETE_ENTITY: {"name"},
    AgentChangeType.CREATE_ENTRY: {
        "kind",
        "date",
        "name",
        "amount_minor",
        "currency_code",
        "from_entity",
        "to_entity",
        "tags",
        "markdown_notes",
    },
    AgentChangeType.UPDATE_ENTRY: {"selector", "patch"},
    AgentChangeType.DELETE_ENTRY: {"selector"},
}


def parse_patch_path(path: str) -> list[str]:
    normalized = normalize_required_text(path)
    parts = [part.strip() for part in normalized.split(".")]
    if any(not part for part in parts):
        raise ValueError("patch_map path segments cannot be empty")
    return parts


def validate_patch_map_paths(change_type: AgentChangeType, patch_map: dict[str, Any]) -> None:
    allowed_roots = PROPOSAL_MUTABLE_ROOTS.get(change_type)
    if not allowed_roots:
        raise ValueError(f"unsupported proposal change type: {change_type.value}")
    disallowed = sorted(path for path in patch_map if parse_patch_path(path)[0] not in allowed_roots)
    if disallowed:
        allowed = ", ".join(sorted(allowed_roots))
        raise ValueError(
            f"patch_map includes non-editable fields for {change_type.value}: {', '.join(disallowed)}. "
            f"Allowed roots: {allowed}"
        )
