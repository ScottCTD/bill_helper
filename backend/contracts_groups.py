# CALLING SPEC:
# - Purpose: provide the `contracts_groups` module.
# - Inputs: callers that import `backend/contracts_groups.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `contracts_groups`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.enums_finance import GroupMemberRole, GroupType
from backend.validation.contract_fields import NonEmptyPatchModel, OptionalRequiredText, RequiredLooseText


class GroupCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredLooseText = Field(min_length=1, max_length=255)
    group_type: GroupType


class GroupPatch(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalRequiredText = Field(default=None, min_length=1, max_length=255)


class EntryGroupMemberTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["entry"] = "entry"
    entry_id: str


class ChildGroupMemberTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: Literal["child_group"] = "child_group"
    group_id: str


type GroupMemberTarget = Annotated[
    EntryGroupMemberTarget | ChildGroupMemberTarget,
    Field(discriminator="target_type"),
]


class GroupMemberCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: GroupMemberTarget
    member_role: GroupMemberRole | None = None
