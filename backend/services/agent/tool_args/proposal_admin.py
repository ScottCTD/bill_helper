from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from backend.enums_finance import GroupMemberRole
from backend.services.agent.change_contracts import (
    CreateGroupMemberPayload,
    DeleteGroupMemberPayload,
    EntryReferencePayload,
    GroupReferencePayload,
    normalize_group_member_reference_payload,
)
from backend.services.agent.payload_normalization import normalize_required_text


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
        return normalize_group_member_reference_payload(value)

    @model_validator(mode="after")
    def validate_targets(self) -> ProposeUpdateGroupMembershipArgs:
        payload = self.model_dump(mode="json", exclude_unset=True)
        if self.action == "add":
            CreateGroupMemberPayload.model_validate(payload)
        else:
            DeleteGroupMemberPayload.model_validate(payload)
        return self
