from __future__ import annotations

import pytest

from backend.enums_agent import AgentChangeType
from backend.services.agent.change_contracts import (
    validate_change_payload,
    validate_patch_map_paths,
)


def test_validate_change_payload_normalizes_create_entry_contract() -> None:
    payload = {
        "kind": "EXPENSE",
        "date": "2026-01-10",
        "name": "  Coffee  ",
        "amount_minor": 450,
        "currency_code": "cad",
        "from_entity": " Main Checking ",
        "to_entity": "Coffee Shop",
        "tags": ["Food", " food ", "cafe"],
        "markdown_notes": "Morning purchase",
    }

    parsed = validate_change_payload(AgentChangeType.CREATE_ENTRY, payload)
    assert parsed.currency_code == "CAD"
    assert parsed.name == "Coffee"
    assert parsed.from_entity == "Main Checking"
    assert parsed.tags == ["cafe", "food"]


def test_validate_patch_map_paths_rejects_non_mutable_roots() -> None:
    with pytest.raises(ValueError):
        validate_patch_map_paths(
            AgentChangeType.UPDATE_ENTRY,
            {"non_editable.field": "value"},
        )


def test_validate_change_payload_normalizes_group_payloads() -> None:
    create_group = validate_change_payload(
        AgentChangeType.CREATE_GROUP,
        {
            "name": "  Monthly Bills  ",
            "group_type": "RECURRING",
        },
    )
    assert create_group.name == "Monthly Bills"
    assert create_group.group_type.value == "RECURRING"

    create_member = validate_change_payload(
        AgentChangeType.CREATE_GROUP_MEMBER,
        {
            "action": "add",
            "group_ref": {"group_id": " ABCD1234 "},
            "entry_ref": {"entry_id": " efgh5678 "},
            "member_role": "CHILD",
        },
    )
    assert create_member.group_ref.group_id == "abcd1234"
    assert create_member.entry_ref is not None
    assert create_member.entry_ref.entry_id == "efgh5678"
    assert create_member.member_role.value == "CHILD"


def test_validate_change_payload_rejects_pending_refs_for_remove_group_member() -> None:
    with pytest.raises(ValueError, match="existing group_id references"):
        validate_change_payload(
            AgentChangeType.DELETE_GROUP_MEMBER,
            {
                "action": "remove",
                "group_ref": {"create_group_proposal_id": "proposal-1234"},
                "entry_ref": {"entry_id": "entry-1234"},
            },
        )
