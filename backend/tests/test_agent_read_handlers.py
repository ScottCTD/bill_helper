from __future__ import annotations

from sqlalchemy import func, select

from backend.database import get_session_maker
from backend.models_finance import User
from backend.services.agent.read_tools.catalog import list_accounts
from backend.services.agent.read_tools.groups import list_groups
from backend.services.agent.tool_args import ListAccountsArgs, ListGroupsArgs
from backend.services.agent.tool_types import ToolContext


def _user_count(db) -> int:
    return int(db.scalar(select(func.count(User.id))) or 0)


def test_list_accounts_does_not_bootstrap_runtime_settings_user() -> None:
    db = get_session_maker()()
    try:
        result = list_accounts(ToolContext(db=db, run_id="run-1"), ListAccountsArgs())

        assert result.output_json["status"] == "OK"
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

        assert result.output_json["status"] == "OK"
        assert result.output_json["groups"] == []
        assert _user_count(db) == 0
    finally:
        db.close()
