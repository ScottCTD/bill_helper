from __future__ import annotations

import pytest

from backend.database import get_session_maker
from backend.services.agent.apply.entries import apply_update_entry
from backend.services.agent.change_contracts.entries import UpdateEntryPatchPayload, UpdateEntryPayload
from backend.services.agent.entry_references import (
    find_entries_by_exact_id,
    find_entries_by_public_id_prefix,
)
from backend.services.users import find_user_by_name
from backend.tests.test_entries import create_account, create_entry


def test_entry_reference_helpers_split_exact_and_prefix_lookup(client) -> None:
    account_id = create_account(client)
    entry = create_entry(client, account_id, "Coffee")
    public_id = entry["id"][:8]

    db = get_session_maker()()
    try:
        assert find_entries_by_exact_id(db, public_id) == []
        prefix_matches = find_entries_by_public_id_prefix(db, public_id)
        assert [match.id for match in prefix_matches] == [entry["id"]]
        exact_matches = find_entries_by_exact_id(db, entry["id"])
        assert [match.id for match in exact_matches] == [entry["id"]]
    finally:
        db.close()


def test_entry_reference_helpers_scope_matches_by_principal(client) -> None:
    admin_account_id = create_account(client, name="Admin Checking")
    admin_entry = create_entry(client, admin_account_id, "Admin Coffee")

    alice_headers = {"X-Bill-Helper-Principal": "alice"}
    alice_account_id = create_account(client, name="Alice Checking", headers=alice_headers)
    alice_entry = create_entry(client, alice_account_id, "Alice Coffee", headers=alice_headers)

    db = get_session_maker()()
    try:
        alice = find_user_by_name(db, "alice")
        assert alice is not None

        assert find_entries_by_exact_id(
            db,
            admin_entry["id"],
            principal_user_id=alice.id,
            is_admin=False,
        ) == []

        alice_matches = find_entries_by_exact_id(
            db,
            alice_entry["id"],
            principal_user_id=alice.id,
            is_admin=False,
        )
        assert [match.id for match in alice_matches] == [alice_entry["id"]]

        prefix_matches = find_entries_by_public_id_prefix(
            db,
            admin_entry["id"][:8],
            principal_user_id=alice.id,
            is_admin=False,
        )
        assert prefix_matches == []
    finally:
        db.close()


def test_apply_update_entry_uses_reviewer_scope(client) -> None:
    admin_account_id = create_account(client, name="Admin Checking")
    admin_entry = create_entry(client, admin_account_id, "Admin Coffee")

    db = get_session_maker()()
    try:
        with pytest.raises(ValueError, match="Entry id did not match any entry"):
            apply_update_entry(
                db,
                UpdateEntryPayload(
                    entry_id=admin_entry["id"],
                    patch=UpdateEntryPatchPayload(name="Hidden update"),
                ),
                actor_name="alice",
            )
    finally:
        db.close()
