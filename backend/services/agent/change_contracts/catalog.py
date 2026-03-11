from __future__ import annotations

from datetime import date as DateValue
from decimal import Decimal

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


class ProposeCreateSnapshotArgs(BaseModel):
    account_id: str = Field(min_length=4, max_length=36)
    snapshot_at: DateValue
    balance: Decimal
    note: str | None = Field(default=None, max_length=2000)


class SnapshotTargetPayload(BaseModel):
    id: str = Field(min_length=4, max_length=36)
    snapshot_at: DateValue
    balance_minor: int
    note: str | None = Field(default=None, max_length=2000)


class SnapshotCreatePayload(BaseModel):
    account_id: str = Field(min_length=4, max_length=36)
    account_name: RequiredEntityName = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3)
    snapshot_at: DateValue
    balance_minor: int
    note: str | None = Field(default=None, max_length=2000)


class ProposeDeleteSnapshotArgs(BaseModel):
    account_id: str = Field(min_length=4, max_length=36)
    snapshot_id: str = Field(min_length=4, max_length=36)


class SnapshotDeletePayload(BaseModel):
    account_id: str = Field(min_length=4, max_length=36)
    account_name: RequiredEntityName = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3)
    snapshot_id: str = Field(min_length=4, max_length=36)
    target: SnapshotTargetPayload
    impact_preview: dict[str, object] | None = None
