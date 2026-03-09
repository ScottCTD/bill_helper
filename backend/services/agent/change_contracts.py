from __future__ import annotations

from datetime import date as DateValue
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.enums_agent import AgentChangeType
from backend.enums_finance import EntryKind, GroupMemberRole, GroupType
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


def normalize_optional_reference_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = normalize_loose_text(value)
    return normalized.lower() if normalized is not None else None


def normalize_optional_proposal_id(value: str | None) -> str | None:
    return normalize_optional_reference_id(value)


def normalize_entry_reference_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    if "entry_id" in normalized:
        normalized["entry_id"] = normalize_optional_reference_id(normalized.get("entry_id"))
    normalized["selector"] = normalize_object_json_string(normalized.get("selector"))
    return normalized


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


class CreateAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3)
    is_active: bool = True
    markdown_body: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str) -> str:
        return normalize_required_text(value).upper()


class UpdateAccountPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    currency_code: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
    markdown_body: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("currency_code")
    @classmethod
    def normalize_currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value).upper()

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateAccountPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    patch: UpdateAccountPatchPayload

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = normalize_entity_name(value)
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized


class DeleteAccountPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)

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


class GroupReferencePayload(BaseModel):
    group_id: str | None = Field(default=None, min_length=4, max_length=36)
    create_group_proposal_id: str | None = Field(default=None, min_length=4, max_length=36)

    @field_validator("group_id")
    @classmethod
    def normalize_group_id(cls, value: str | None) -> str | None:
        return normalize_optional_reference_id(value)

    @field_validator("create_group_proposal_id")
    @classmethod
    def normalize_create_group_proposal_id(cls, value: str | None) -> str | None:
        return normalize_optional_proposal_id(value)

    @model_validator(mode="after")
    def ensure_reference_present(self) -> GroupReferencePayload:
        if (self.group_id is None) == (self.create_group_proposal_id is None):
            raise ValueError("exactly one of group_id or create_group_proposal_id is required")
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


class CreateGroupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    group_type: GroupType

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return normalize_required_text(value)


class UpdateGroupPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_required_text(value)

    @model_validator(mode="after")
    def ensure_any_field_set(self) -> UpdateGroupPatchPayload:
        if not self.model_fields_set:
            raise ValueError("patch must include at least one field")
        return self


class UpdateGroupPayload(BaseModel):
    group_id: str = Field(min_length=4, max_length=36)
    patch: UpdateGroupPatchPayload

    @field_validator("group_id")
    @classmethod
    def normalize_group_id(cls, value: str) -> str:
        normalized = normalize_optional_reference_id(value)
        if normalized is None:
            raise ValueError("group_id is required")
        return normalized

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["patch"] = normalize_object_json_string(normalized.get("patch"))
        return normalized


class DeleteGroupPayload(BaseModel):
    group_id: str = Field(min_length=4, max_length=36)

    @field_validator("group_id")
    @classmethod
    def normalize_group_id(cls, value: str) -> str:
        normalized = normalize_optional_reference_id(value)
        if normalized is None:
            raise ValueError("group_id is required")
        return normalized


class CreateGroupMemberPayload(BaseModel):
    action: Literal["add"] = "add"
    group_ref: GroupReferencePayload
    entry_ref: EntryReferencePayload | None = None
    child_group_ref: GroupReferencePayload | None = None
    member_role: GroupMemberRole | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["group_ref"] = normalize_object_json_string(normalized.get("group_ref"))
        normalized["entry_ref"] = normalize_object_json_string(normalized.get("entry_ref"))
        normalized["child_group_ref"] = normalize_object_json_string(normalized.get("child_group_ref"))
        return normalized

    @model_validator(mode="after")
    def ensure_target_present(self) -> CreateGroupMemberPayload:
        if (self.entry_ref is None) == (self.child_group_ref is None):
            raise ValueError("exactly one of entry_ref or child_group_ref is required")
        return self


class DeleteGroupMemberPayload(BaseModel):
    action: Literal["remove"] = "remove"
    group_ref: GroupReferencePayload
    entry_ref: EntryReferencePayload | None = None
    child_group_ref: GroupReferencePayload | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalized = dict(value)
        normalized["group_ref"] = normalize_object_json_string(normalized.get("group_ref"))
        normalized["entry_ref"] = normalize_object_json_string(normalized.get("entry_ref"))
        normalized["child_group_ref"] = normalize_object_json_string(normalized.get("child_group_ref"))
        return normalized

    @model_validator(mode="after")
    def ensure_existing_target_present(self) -> DeleteGroupMemberPayload:
        if (self.entry_ref is None) == (self.child_group_ref is None):
            raise ValueError("exactly one of entry_ref or child_group_ref is required")
        if self.group_ref.create_group_proposal_id is not None:
            raise ValueError("remove action only supports existing group_id references")
        if self.entry_ref is not None and self.entry_ref.create_entry_proposal_id is not None:
            raise ValueError("remove action only supports existing entry_id references")
        if self.child_group_ref is not None and self.child_group_ref.create_group_proposal_id is not None:
            raise ValueError("remove action only supports existing child group_id references")
        return self


CHANGE_PAYLOAD_MODELS: dict[AgentChangeType, type[BaseModel]] = {
    AgentChangeType.CREATE_TAG: CreateTagPayload,
    AgentChangeType.UPDATE_TAG: UpdateTagPayload,
    AgentChangeType.DELETE_TAG: DeleteTagPayload,
    AgentChangeType.CREATE_ENTITY: CreateEntityPayload,
    AgentChangeType.UPDATE_ENTITY: UpdateEntityPayload,
    AgentChangeType.DELETE_ENTITY: DeleteEntityPayload,
    AgentChangeType.CREATE_ACCOUNT: CreateAccountPayload,
    AgentChangeType.UPDATE_ACCOUNT: UpdateAccountPayload,
    AgentChangeType.DELETE_ACCOUNT: DeleteAccountPayload,
    AgentChangeType.CREATE_ENTRY: CreateEntryPayload,
    AgentChangeType.UPDATE_ENTRY: UpdateEntryPayload,
    AgentChangeType.DELETE_ENTRY: DeleteEntryPayload,
    AgentChangeType.CREATE_GROUP: CreateGroupPayload,
    AgentChangeType.UPDATE_GROUP: UpdateGroupPayload,
    AgentChangeType.DELETE_GROUP: DeleteGroupPayload,
    AgentChangeType.CREATE_GROUP_MEMBER: CreateGroupMemberPayload,
    AgentChangeType.DELETE_GROUP_MEMBER: DeleteGroupMemberPayload,
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
    AgentChangeType.CREATE_ACCOUNT: {"name", "currency_code", "is_active", "markdown_body"},
    AgentChangeType.UPDATE_ACCOUNT: {"name", "patch"},
    AgentChangeType.DELETE_ACCOUNT: {"name"},
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
    AgentChangeType.UPDATE_ENTRY: {"entry_id", "selector", "patch"},
    AgentChangeType.DELETE_ENTRY: {"entry_id", "selector"},
    AgentChangeType.CREATE_GROUP: {"name", "group_type"},
    AgentChangeType.UPDATE_GROUP: {"group_id", "patch"},
    AgentChangeType.DELETE_GROUP: {"group_id"},
    AgentChangeType.CREATE_GROUP_MEMBER: {"action", "group_ref", "entry_ref", "child_group_ref", "member_role"},
    AgentChangeType.DELETE_GROUP_MEMBER: {"action", "group_ref", "entry_ref", "child_group_ref"},
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
