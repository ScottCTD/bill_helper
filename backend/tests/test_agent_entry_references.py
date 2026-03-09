from __future__ import annotations

from backend.database import get_session_maker
from backend.services.agent.entry_references import (
    find_entries_by_exact_id,
    find_entries_by_public_id_prefix,
)
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
