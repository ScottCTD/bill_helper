from __future__ import annotations

from sqlalchemy import func, select

from backend.database import get_session_maker
from backend.models_finance import User
from backend.services.agent.read_tools.accounts import get_reconciliation, list_snapshots
from backend.services.agent.read_tools.catalog import list_accounts
from backend.services.agent.read_tools.entries import list_entries
from backend.services.agent.read_tools.groups import list_groups
from backend.services.agent.tool_args import (
    GetReconciliationArgs,
    ListAccountsArgs,
    ListEntriesArgs,
    ListGroupsArgs,
    ListSnapshotsArgs,
)
from backend.services.agent.tool_types import ToolContext
from backend.tests.test_entries import create_account, create_entry


def _user_count(db) -> int:
    return int(db.scalar(select(func.count(User.id))) or 0)


def test_list_accounts_does_not_bootstrap_runtime_settings_user() -> None:
    db = get_session_maker()()
    try:
        result = list_accounts(ToolContext(db=db, run_id="run-1"), ListAccountsArgs())

        assert result.output_json["status"] == "ok"
        assert result.output_json["accounts"] == []
        assert _user_count(db) == 0
    finally:
        db.close()


def test_list_groups_does_not_bootstrap_context_principal_user() -> None:
    db = get_session_maker()()
    try:
        result = list_groups(
            ToolContext(db=db, run_id="run-1", principal_name="alice", principal_user_id=None),
            ListGroupsArgs(),
        )

        assert result.output_json["status"] == "ok"
        assert result.output_json["groups"] == []
        assert _user_count(db) == 0
    finally:
        db.close()


def test_list_entries_respects_tool_principal_scope(client) -> None:
    admin_account_id = create_account(client, name="Admin Checking")
    create_entry(client, admin_account_id, "Admin Coffee")

    alice_headers = {"X-Bill-Helper-Principal": "alice"}
    alice_account_id = create_account(client, name="Alice Checking", headers=alice_headers)
    alice_entry = create_entry(client, alice_account_id, "Alice Coffee", headers=alice_headers)

    db = get_session_maker()()
    try:
        alice = db.scalar(select(User).where(User.name == "alice"))
        assert alice is not None

        result = list_entries(
            ToolContext(db=db, run_id="run-1", principal_name="alice", principal_user_id=alice.id),
            ListEntriesArgs(limit=10),
        )

        records = result.output_json["entries"]
        assert [record["entry_id"] for record in records] == [alice_entry["id"][:8]]
    finally:
        db.close()


def test_snapshot_read_tools_return_interval_reconciliation(client) -> None:
    account_id = create_account(client, name="Checking")
    first_snapshot = client.post(
        f"/api/v1/accounts/{account_id}/snapshots",
        json={"snapshot_at": "2026-01-01", "balance_minor": 100000, "note": "Opening"},
    )
    first_snapshot.raise_for_status()
    second_snapshot = client.post(
        f"/api/v1/accounts/{account_id}/snapshots",
        json={"snapshot_at": "2026-02-01", "balance_minor": 90000, "note": "Closing"},
    )
    second_snapshot.raise_for_status()
    entry_response = client.post(
        "/api/v1/entries",
        json={
            "account_id": account_id,
            "kind": "EXPENSE",
            "occurred_at": "2026-01-15",
            "name": "Coffee",
            "amount_minor": 1200,
            "currency_code": "USD",
            "tags": ["food"],
        },
    )
    entry_response.raise_for_status()

    db = get_session_maker()()
    try:
        context = ToolContext(db=db, run_id="run-1")

        snapshots_result = list_snapshots(context, ListSnapshotsArgs(account_id=account_id, limit=10))
        assert snapshots_result.output_json["snapshots"][0]["snapshot_at"] == "2026-02-01"

        reconciliation_result = get_reconciliation(
            context,
            GetReconciliationArgs(account_id=account_id, as_of="2026-02-15"),
        )
        intervals = reconciliation_result.output_json["reconciliation"]["intervals"]
        assert intervals[0]["bank_change_minor"] == -10000
        assert intervals[0]["tracked_change_minor"] == -1200
        assert intervals[1]["is_open"] is True
    finally:
        db.close()
