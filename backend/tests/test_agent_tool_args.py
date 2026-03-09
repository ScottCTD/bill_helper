from __future__ import annotations

import pytest

from backend.services.agent.tool_args import ProposeUpdateGroupMembershipArgs


def test_propose_update_group_membership_args_normalize_stringified_refs() -> None:
    parsed = ProposeUpdateGroupMembershipArgs.model_validate(
        {
            "action": "add",
            "group_ref": '{"group_id": " ABCD1234 "}',
            "entry_ref": '{"entry_id": " efgh5678 "}',
            "member_role": "CHILD",
        }
    )

    assert parsed.group_ref.group_id == "abcd1234"
    assert parsed.entry_ref is not None
    assert parsed.entry_ref.entry_id == "efgh5678"
    assert parsed.member_role is not None
    assert parsed.member_role.value == "CHILD"


def test_propose_update_group_membership_args_reject_pending_refs_for_remove() -> None:
    with pytest.raises(ValueError, match="existing group_id references"):
        ProposeUpdateGroupMembershipArgs.model_validate(
            {
                "action": "remove",
                "group_ref": {"create_group_proposal_id": "proposal-1234"},
                "entry_ref": {"entry_id": "entry-1234"},
            }
        )
