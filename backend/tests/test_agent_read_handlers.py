from __future__ import annotations

from sqlalchemy import func, select

from backend.database import get_session_maker
from backend.models_finance import User
from backend.services.agent.read_tools.catalog import list_accounts
from backend.services.agent.read_tools.entries import list_entries
from backend.services.agent.read_tools.groups import list_groups
from backend.services.agent.tool_args import ListAccountsArgs, ListEntriesArgs, ListGroupsArgs
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
