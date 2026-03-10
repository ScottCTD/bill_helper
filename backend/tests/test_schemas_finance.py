from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.schemas_finance import GroupMemberCreate, TagUpdate, TaxonomyTermCreate, UserUpdate


def test_taxonomy_term_create_forbids_parent_term_field() -> None:
    with pytest.raises(ValidationError):
        TaxonomyTermCreate(name="food", parent_term_id="root")


def test_update_schemas_reject_empty_patch_payloads() -> None:
    with pytest.raises(ValidationError):
        TagUpdate()
    with pytest.raises(ValidationError):
        UserUpdate()


def test_group_member_create_uses_typed_target_payload() -> None:
    payload = GroupMemberCreate.model_validate(
        {
            "target": {
                "target_type": "entry",
                "entry_id": "entry-1234",
            }
        }
    )

    assert payload.target.target_type == "entry"
