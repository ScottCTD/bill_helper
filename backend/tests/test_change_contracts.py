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
