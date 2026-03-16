# CALLING SPEC:
# - Purpose: implement focused service logic for `proposal_admin`.
# - Inputs: callers that import `backend/services/agent/tool_args/proposal_admin.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `proposal_admin`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from backend.enums_finance import GroupMemberRole
from backend.services.agent.change_contracts.groups import (
    CreateGroupMemberPayload,
    DeleteGroupMemberPayload,
    GroupMemberTargetPayload,
    GroupReferencePayload,
    normalize_group_member_payload,
)
class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposeUpdateGroupMembershipArgs(ToolArgsModel):
    action: Literal["add", "remove"]
    group_ref: GroupReferencePayload
    target: GroupMemberTargetPayload
    member_role: GroupMemberRole | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_nested_object_args(cls, value: object) -> object:
        return normalize_group_member_payload(value)

    @model_validator(mode="after")
    def validate_targets(self) -> ProposeUpdateGroupMembershipArgs:
        payload = self.model_dump(mode="json", exclude_unset=True)
        if self.action == "add":
            CreateGroupMemberPayload.model_validate(payload)
        else:
            DeleteGroupMemberPayload.model_validate(payload)
        return self
