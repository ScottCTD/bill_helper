from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from backend.enums_finance import GroupMemberRole, GroupType
from backend.services.agent.change_contracts.common import (
    normalize_object_json_string,
    normalize_optional_proposal_id,
    normalize_optional_reference_id,
)
from backend.services.agent.change_contracts.entries import EntryReferencePayload
from backend.validation.contract_fields import NonEmptyPatchModel, OptionalRequiredText, RequiredLooseText


def normalize_group_member_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    normalized = dict(value)
    normalized["group_ref"] = normalize_object_json_string(normalized.get("group_ref"))
    target = normalize_object_json_string(normalized.get("target"))
    if not isinstance(target, dict):
        legacy_entry_ref = normalize_object_json_string(normalized.get("entry_ref"))
        legacy_child_group_ref = normalize_object_json_string(normalized.get("child_group_ref"))
        if legacy_entry_ref is not None and legacy_child_group_ref is None:
            target = {"target_type": "entry", "entry_ref": legacy_entry_ref}
        elif legacy_child_group_ref is not None and legacy_entry_ref is None:
            target = {"target_type": "child_group", "group_ref": legacy_child_group_ref}
    if isinstance(target, dict):
        normalized_target = dict(target)
        normalized_target["entry_ref"] = normalize_object_json_string(normalized_target.get("entry_ref"))
        normalized_target["group_ref"] = normalize_object_json_string(normalized_target.get("group_ref"))
        normalized["target"] = normalized_target
    normalized.pop("entry_ref", None)
    normalized.pop("child_group_ref", None)
    return normalized


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


class EntryGroupMemberTargetPayload(BaseModel):
    target_type: Literal["entry"] = "entry"
    entry_ref: EntryReferencePayload


class ChildGroupMemberTargetPayload(BaseModel):
    target_type: Literal["child_group"] = "child_group"
    group_ref: GroupReferencePayload


type GroupMemberTargetPayload = Annotated[
    EntryGroupMemberTargetPayload | ChildGroupMemberTargetPayload,
    Field(discriminator="target_type"),
]


GROUP_MEMBER_TARGET_ADAPTER = TypeAdapter(GroupMemberTargetPayload)


def parse_group_member_target_payload(value: Any) -> GroupMemberTargetPayload:
    return GROUP_MEMBER_TARGET_ADAPTER.validate_python(value)


class CreateGroupPayload(BaseModel):
    name: RequiredLooseText = Field(min_length=1, max_length=255)
    group_type: GroupType


class UpdateGroupPatchPayload(NonEmptyPatchModel):
    name: OptionalRequiredText = Field(default=None, min_length=1, max_length=255)


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
    target: GroupMemberTargetPayload
    member_role: GroupMemberRole | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        return normalize_group_member_payload(value)


class DeleteGroupMemberPayload(BaseModel):
    action: Literal["remove"] = "remove"
    group_ref: GroupReferencePayload
    target: GroupMemberTargetPayload

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: Any) -> Any:
        return normalize_group_member_payload(value)

    @model_validator(mode="after")
    def ensure_existing_target_present(self) -> DeleteGroupMemberPayload:
        if self.group_ref.create_group_proposal_id is not None:
            raise ValueError("remove action only supports existing group_id references")
        if (
            isinstance(self.target, EntryGroupMemberTargetPayload)
            and self.target.entry_ref.create_entry_proposal_id is not None
        ):
            raise ValueError("remove action only supports existing entry_id references")
        if (
            isinstance(self.target, ChildGroupMemberTargetPayload)
            and self.target.group_ref.create_group_proposal_id is not None
        ):
            raise ValueError("remove action only supports existing child group_id references")
        return self
