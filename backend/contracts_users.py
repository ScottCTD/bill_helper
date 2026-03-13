# CALLING SPEC:
# - Purpose: provide the `contracts_users` module.
# - Inputs: callers that import `backend/contracts_users.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `contracts_users`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.validation.contract_fields import NonEmptyPatchModel, OptionalRequiredText, RequiredLooseText


class UserCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredLooseText = Field(min_length=1, max_length=255)
    password: RequiredLooseText = Field(min_length=1, max_length=255)
    is_admin: bool = False


class UserPatch(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalRequiredText = Field(default=None, min_length=1, max_length=255)
    is_admin: bool | None = None


class UserPasswordResetCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_password: RequiredLooseText = Field(min_length=1, max_length=255)


class UserPasswordChangeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: RequiredLooseText = Field(min_length=1, max_length=255)
    new_password: RequiredLooseText = Field(min_length=1, max_length=255)
