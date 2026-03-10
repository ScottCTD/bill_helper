from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.validation.contract_fields import NonEmptyPatchModel, OptionalRequiredText, RequiredLooseText


class UserCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredLooseText = Field(min_length=1, max_length=255)


class UserPatch(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalRequiredText = Field(default=None, min_length=1, max_length=255)
