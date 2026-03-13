# CALLING SPEC:
# - Purpose: implement focused service logic for `catalog`.
# - Inputs: callers that import `backend/services/agent/change_contracts/catalog.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `catalog`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from datetime import date as DateValue
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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


class ChangePayloadModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateTagPayload(TagCreateCore):
    type: RequiredCategory = Field(min_length=1, max_length=100)


class UpdateTagPatchPayload(TagPatchCore):
    pass


class UpdateTagPayload(ChangePayloadModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)
    patch: UpdateTagPatchPayload
    current: dict[str, Any] | None = None


class DeleteTagPayload(ChangePayloadModel):
    name: RequiredTagName = Field(min_length=1, max_length=64)


class CreateEntityPayload(EntityCreateCore):
    category: RequiredCategory = Field(min_length=1, max_length=100)


class UpdateEntityPatchPayload(EntityPatchCore):
    pass


class UpdateEntityPayload(ChangePayloadModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    patch: UpdateEntityPatchPayload
    current: dict[str, Any] | None = None


class DeleteEntityPayload(ChangePayloadModel):
    name: RequiredEntityName = Field(min_length=1, max_length=255)
    impact_preview: dict[str, Any] | None = None


class CreateAccountPayload(AccountCreateCore):
    pass


class UpdateAccountPatchPayload(AccountPatchCore):
    pass


class UpdateAccountPayload(ChangePayloadModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
    patch: UpdateAccountPatchPayload
    current: dict[str, Any] | None = None


class DeleteAccountPayload(ChangePayloadModel):
    name: RequiredEntityName = Field(min_length=1, max_length=200)
    impact_preview: dict[str, Any] | None = None


class ProposeCreateSnapshotArgs(ChangePayloadModel):
    account_id: str = Field(min_length=4, max_length=36)
    snapshot_at: DateValue
    balance: Decimal
    note: str | None = Field(default=None, max_length=2000)


class SnapshotTargetPayload(ChangePayloadModel):
    id: str = Field(min_length=4, max_length=36)
    snapshot_at: DateValue
    balance_minor: int
    note: str | None = Field(default=None, max_length=2000)


class SnapshotCreatePayload(ChangePayloadModel):
    account_id: str = Field(min_length=4, max_length=36)
    account_name: RequiredEntityName = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3)
    snapshot_at: DateValue
    balance_minor: int
    note: str | None = Field(default=None, max_length=2000)


class ProposeDeleteSnapshotArgs(ChangePayloadModel):
    account_id: str = Field(min_length=4, max_length=36)
    snapshot_id: str = Field(min_length=4, max_length=36)


class SnapshotDeletePayload(ChangePayloadModel):
    account_id: str = Field(min_length=4, max_length=36)
    account_name: RequiredEntityName = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=3)
    snapshot_id: str = Field(min_length=4, max_length=36)
    target: SnapshotTargetPayload
    impact_preview: dict[str, object] | None = None
