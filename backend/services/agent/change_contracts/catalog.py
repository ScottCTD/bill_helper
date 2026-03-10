from __future__ import annotations

from pydantic import BaseModel, Field

from backend.services.finance_contracts import (
    AccountCreateCore,
    AccountPatchCore,
    EntityCreateCore,
    EntityPatchCore,
    TagCreateCore,
    TagPatchCore,
)
from backend.validation.contract_fields import (
    RequiredCategory,
    RequiredEntityName,
    RequiredTagName,
)


class CreateTagPayload(TagCreateCore):
    type: RequiredCategory = Field(min_length=1, max_length=100)


class UpdateTagPatchPayload(TagPatchCore):
    pass


class UpdateTagPayload(BaseModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)
    patch: UpdateTagPatchPayload


class DeleteTagPayload(BaseModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)


class CreateEntityPayload(EntityCreateCore):
    category: RequiredCategory = Field(min_length=1, max_length=100)


class UpdateEntityPatchPayload(EntityPatchCore):
    pass


class UpdateEntityPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    patch: UpdateEntityPatchPayload


class DeleteEntityPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)


class CreateAccountPayload(AccountCreateCore):
    pass


class UpdateAccountPatchPayload(AccountPatchCore):
    pass


class UpdateAccountPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
    patch: UpdateAccountPatchPayload


class DeleteAccountPayload(BaseModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
