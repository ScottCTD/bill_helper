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


class AccountCreateCore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredEntityName = Field(min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: RequiredCurrencyCode = Field(min_length=3, max_length=3)
    is_active: bool = True


class AccountCreateCommand(AccountCreateCore):
    owner_user_id: str | None = Field(default=None, min_length=1)


class AccountPatchCore(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalEntityName = Field(default=None, min_length=1, max_length=200)
    markdown_body: str | None = None
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


class AccountPatch(AccountPatchCore):
    owner_user_id: str | None = Field(default=None, min_length=1)

    def includes(self, field: AccountPatchField) -> bool:
        return field in self.model_fields_set


class EntityCreateCore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredEntityName = Field(min_length=1, max_length=255)
    category: OptionalCategory = Field(default=None, max_length=100)


class EntityCreateCommand(EntityCreateCore):
    pass


class EntityPatchCore(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalEntityName = Field(default=None, min_length=1, max_length=255)
    category: OptionalCategory = Field(default=None, max_length=100)


class EntityPatch(EntityPatchCore):
    pass


class TagCreateCore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RequiredTagName = Field(min_length=1, max_length=64)
    type: OptionalCategory = Field(default=None, max_length=100)


class TagCreateCommand(TagCreateCore):
    color: OptionalLooseText = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)


class TagPatchCore(NonEmptyPatchModel):
    model_config = ConfigDict(extra="forbid")

    name: OptionalTagName = Field(default=None, min_length=1, max_length=64)
    type: OptionalCategory = Field(default=None, max_length=100)


class TagPatch(TagPatchCore):
    color: OptionalLooseText = Field(default=None, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
