from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from backend.database import get_session_maker
from backend.models_agent import AgentRun, AgentThread
from backend.services.agent.tool_args.terminal import RunTerminalArgs
from backend.services.agent.tool_types import ToolContext
from backend.services.agent.terminal import run_terminal
from backend.tests.agent_test_utils import create_thread, patch_model, send_message


@dataclass(frozen=True, slots=True)
class _FakeWorkspaceSpec:
    docker_binary: str = "docker"
    container_name: str = "bill-helper-sandbox-user-1"


def test_run_terminal_injects_cli_context_and_scrubs_token(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for terminal tool context.")
    db = get_session_maker()()
    captured: dict[str, object] = {}
    try:
        run_row = db.get(AgentRun, run["id"])
        assert run_row is not None
        thread_row = db.get(AgentThread, run_row.thread_id)
        assert thread_row is not None

        monkeypatch.setattr(
            "backend.services.agent.terminal.start_user_workspace",
            lambda **_kwargs: _FakeWorkspaceSpec(),
        )

        def fake_exec_in_container(**kwargs):
            captured.update(kwargs)
            token = kwargs["env"]["BH_AUTH_TOKEN"]
            return SimpleNamespace(
                returncode=0,
                stdout=f"token={token}",
                stderr="",
            )

        monkeypatch.setattr(
            "backend.services.agent.terminal.docker_cli.exec_in_container",
            fake_exec_in_container,
        )

        result = run_terminal(
            ToolContext(
                db=db,
                run_id=run["id"],
                principal_name="admin",
                principal_user_id=thread_row.owner_user_id,
                principal_is_admin=False,
            ),
            RunTerminalArgs(command="bh status"),
        )
    finally:
        db.close()

    assert result.status.value == "ok"
    assert captured["command"] == ["bash", "-lc", "bh status"]
    assert captured["workdir"] == "/workspace/scratch"
    assert captured["env"]["BH_THREAD_ID"] == thread["id"]
    assert captured["env"]["BH_RUN_ID"] == run["id"]
    assert captured["env"]["BH_API_BASE_URL"]
    assert captured["env"]["BH_AUTH_TOKEN"]
    assert result.output_json["stdout"] == "token=***"
    assert result.output_json["summary"] == "terminal command completed"


def test_run_terminal_preserves_multiline_command_verbatim(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for terminal context.")
    db = get_session_maker()()
    captured: dict[str, object] = {}
    command = "cat > /tmp/test.txt <<'EOF'\nhello\nEOF\necho done\n"
    try:
        run_row = db.get(AgentRun, run["id"])
        assert run_row is not None
        thread_row = db.get(AgentThread, run_row.thread_id)
        assert thread_row is not None

        monkeypatch.setattr(
            "backend.services.agent.terminal.start_user_workspace",
            lambda **_kwargs: _FakeWorkspaceSpec(),
        )

        def fake_exec_in_container(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                returncode=0,
                stdout="done",
                stderr="",
            )

        monkeypatch.setattr(
            "backend.services.agent.terminal.docker_cli.exec_in_container",
            fake_exec_in_container,
        )

        result = run_terminal(
            ToolContext(
                db=db,
                run_id=run["id"],
                principal_name="admin",
                principal_user_id=thread_row.owner_user_id,
                principal_is_admin=False,
            ),
            RunTerminalArgs(command=command),
        )
    finally:
        db.close()

    assert result.status.value == "ok"
    assert captured["command"] == ["bash", "-lc", command]
    assert result.output_json["summary"] == "terminal command completed"
