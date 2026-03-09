from __future__ import annotations

from pydantic import BaseModel, Field

from backend.validation.contract_fields import (
    NonEmptyPatchModel,
    OptionalCategory,
    OptionalCurrencyCode,
    OptionalEntityName,
    OptionalTagName,
    RequiredCategory,
    RequiredCurrencyCode,
    RequiredEntityName,
    RequiredTagName,
)


class CreateTagPayload(BaseModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)
    type: RequiredCategory = Field(min_length=1, max_length=100)


class UpdateTagPatchPayload(NonEmptyPatchModel):
    name: OptionalTagName = Field(default=None, min_length=1, max_length=64)
    type: OptionalCategory = Field(default=None, max_length=100)


class UpdateTagPayload(BaseModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)
    patch: UpdateTagPatchPayload


class DeleteTagPayload(BaseModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)


class CreateEntityPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    category: RequiredCategory = Field(min_length=1, max_length=100)


class UpdateEntityPatchPayload(NonEmptyPatchModel):
    name: OptionalEntityName = Field(default=None, min_length=1, max_length=255)
    category: OptionalCategory = Field(default=None, max_length=100)


class UpdateEntityPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    patch: UpdateEntityPatchPayload


class DeleteEntityPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)


class CreateAccountPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
    currency_code: RequiredCurrencyCode = Field(min_length=3, max_length=3)
    is_active: bool = True
    markdown_body: str | None = None


class UpdateAccountPatchPayload(NonEmptyPatchModel):
    name: OptionalEntityName = Field(default=None, min_length=1, max_length=200)
    currency_code: OptionalCurrencyCode = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
    markdown_body: str | None = None


class UpdateAccountPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
    patch: UpdateAccountPatchPayload


class DeleteAccountPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
