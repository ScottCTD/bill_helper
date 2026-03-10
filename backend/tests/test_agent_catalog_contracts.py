from __future__ import annotations

from backend.services.agent.change_contracts.catalog import (
    CreateAccountPayload,
    CreateEntityPayload,
    CreateTagPayload,
    UpdateAccountPatchPayload,
    UpdateEntityPatchPayload,
    UpdateTagPatchPayload,
)
from backend.services.finance_contracts import (
    AccountCreateCore,
    AccountPatchCore,
    EntityCreateCore,
    EntityPatchCore,
    TagCreateCore,
    TagPatchCore,
)


def test_agent_catalog_contracts_reuse_finance_contract_bases() -> None:
    assert issubclass(CreateTagPayload, TagCreateCore)
    assert issubclass(UpdateTagPatchPayload, TagPatchCore)
    assert issubclass(CreateEntityPayload, EntityCreateCore)
    assert issubclass(UpdateEntityPatchPayload, EntityPatchCore)
    assert issubclass(CreateAccountPayload, AccountCreateCore)
    assert issubclass(UpdateAccountPatchPayload, AccountPatchCore)
