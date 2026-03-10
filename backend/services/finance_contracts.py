from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.validation.contract_fields import (
    NonEmptyPatchModel,
    OptionalCategory,
    OptionalCurrencyCode,
    OptionalEntityName,
    OptionalLooseText,
    OptionalTagName,
    RequiredCurrencyCode,
    RequiredEntityName,
    RequiredTagName,
)

AccountPatchField = Literal["owner_user_id", "name", "markdown_body", "currency_code", "is_active"]


class AccountCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: str | None = None
    name: RequiredEntityName = Field(min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: RequiredCurrencyCode = Field(min_length=3, max_length=3)
    is_active: bool = True


class AccountPatch(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    owner_user_id: str | None = None
    name: OptionalEntityName = Field(default=None, min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None

    def includes(self, field: AccountPatchField) -> bool:
        return field in self.model_fields_set


class EntityCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredEntityName = Field(min_length=1, max_length=255)
    category: OptionalCategory = Field(default=None, max_length=100)


class EntityPatch(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalEntityName = Field(default=None, min_length=1, max_length=255)
    category: OptionalCategory = Field(default=None, max_length=100)


class TagCreateCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredTagName = Field(min_length=1, max_length=64)
    color: OptionalLooseText = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    type: OptionalCategory = Field(default=None, max_length=100)


class TagPatch(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalTagName = Field(default=None, min_length=1, max_length=64)
    color: OptionalLooseText = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    type: OptionalCategory = Field(default=None, max_length=100)
