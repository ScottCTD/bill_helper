from __future__ import annotations

from dataclasses import dataclass
import json
from types import SimpleNamespace

from backend.database import get_session_maker
from backend.models_agent import AgentRun, AgentThread
from backend.services import docker_cli
from backend.services.agent.read_image import run_read_image
from backend.services.agent.tool_args.read_image import ReadImageArgs
from backend.services.agent.tool_types import ToolContext
from backend.tests.agent_test_utils import create_thread, patch_model, send_message


@dataclass(frozen=True, slots=True)
class _FakeWorkspaceSpec:
    docker_binary: str = "docker"
    container_name: str = "bill-helper-sandbox-user-1"


def test_run_read_image_loads_workspace_images_in_order_and_dedupes(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for image tool context.")
    db = get_session_maker()()
    captured: dict[str, object] = {}
    try:
        run_row = db.get(AgentRun, run["id"])
        assert run_row is not None
        thread_row = db.get(AgentThread, run_row.thread_id)
        assert thread_row is not None

        monkeypatch.setattr(
            "backend.services.agent.read_image.start_user_workspace",
            lambda **_kwargs: _FakeWorkspaceSpec(),
        )
        monkeypatch.setattr(
            "backend.services.agent.read_image.model_supports_vision",
            lambda *_args, **_kwargs: True,
        )

        def fake_exec_in_container(**kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "images": [
                            {
                                "path": "/workspace/uploads/2026-03-22/receipt/raw.png",
                                "mime_type": "image/png",
                                "data_url": "data:image/png;base64,aaa",
                            },
                            {
                                "path": "/workspace/scratch/plot.png",
                                "mime_type": "image/png",
                                "data_url": "data:image/png;base64,bbb",
                            },
                        ]
                    }
                ),
                stderr="",
            )

        monkeypatch.setattr(
            "backend.services.agent.read_image.docker_cli.exec_in_container",
            fake_exec_in_container,
        )

        result = run_read_image(
            ToolContext(
                db=db,
                run_id=run["id"],
                principal_name="admin",
                principal_user_id=thread_row.owner_user_id,
                principal_is_admin=False,
            ),
            ReadImageArgs(
                paths=[
                    "/workspace/uploads/2026-03-22/receipt/raw.png",
                    "/workspace/scratch/plot.png",
                    "/workspace/uploads/2026-03-22/receipt/raw.png",
                ]
            ),
        )
    finally:
        db.close()

    assert result.status.value == "ok"
    assert result.output_json["paths"] == [
        "/workspace/uploads/2026-03-22/receipt/raw.png",
        "/workspace/scratch/plot.png",
    ]
    assert captured["command"][0:2] == ["bash", "-lc"]
    assert json.loads(captured["env"]["BH_READ_IMAGE_PATHS_JSON"]) == [
        "/workspace/uploads/2026-03-22/receipt/raw.png",
        "/workspace/scratch/plot.png",
    ]
    assert isinstance(result.llm_content, list)
    assert result.llm_content[0]["type"] == "text"
    assert result.llm_content[1]["type"] == "image_url"
    assert result.llm_content[2]["type"] == "image_url"


def test_run_read_image_rejects_non_vision_models(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for image tool context.")
    db = get_session_maker()()
    try:
        run_row = db.get(AgentRun, run["id"])
        assert run_row is not None
        thread_row = db.get(AgentThread, run_row.thread_id)
        assert thread_row is not None

        monkeypatch.setattr(
            "backend.services.agent.read_image.model_supports_vision",
            lambda *_args, **_kwargs: False,
        )

        result = run_read_image(
            ToolContext(
                db=db,
                run_id=run["id"],
                principal_name="admin",
                principal_user_id=thread_row.owner_user_id,
                principal_is_admin=False,
            ),
            ReadImageArgs(paths=["/workspace/uploads/2026-03-22/receipt/raw.png"]),
        )
    finally:
        db.close()

    assert result.status.value == "error"
    assert result.output_json["summary"] == (
        "read_image is unavailable because the current model does not support vision."
    )


def test_run_read_image_enforces_configured_path_limit(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for image tool context.")
    db = get_session_maker()()
    try:
        run_row = db.get(AgentRun, run["id"])
        assert run_row is not None
        thread_row = db.get(AgentThread, run_row.thread_id)
        assert thread_row is not None

        monkeypatch.setattr(
            "backend.services.agent.read_image.model_supports_vision",
            lambda *_args, **_kwargs: True,
        )

        result = run_read_image(
            ToolContext(
                db=db,
                run_id=run["id"],
                principal_name="admin",
                principal_user_id=thread_row.owner_user_id,
                principal_is_admin=False,
            ),
            ReadImageArgs(
                paths=[
                    "/workspace/scratch/1.png",
                    "/workspace/scratch/2.png",
                    "/workspace/scratch/3.png",
                    "/workspace/scratch/4.png",
                    "/workspace/scratch/5.png",
                ]
            ),
        )
    finally:
        db.close()

    assert result.status.value == "error"
    assert result.output_json["summary"] == "Too many image paths. Max allowed is 4."


def test_run_read_image_surfaces_container_validation_errors(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for image tool context.")
    db = get_session_maker()()
    try:
        run_row = db.get(AgentRun, run["id"])
        assert run_row is not None
        thread_row = db.get(AgentThread, run_row.thread_id)
        assert thread_row is not None

        monkeypatch.setattr(
            "backend.services.agent.read_image.start_user_workspace",
            lambda **_kwargs: _FakeWorkspaceSpec(),
        )
        monkeypatch.setattr(
            "backend.services.agent.read_image.model_supports_vision",
            lambda *_args, **_kwargs: True,
        )

        def fake_exec_in_container(**_kwargs):
            raise docker_cli.DockerCliError(
                command=["docker", "exec"],
                exit_code=9,
                stderr="",
                stdout=json.dumps({"error": "path must be absolute: relative.png"}),
            )

        monkeypatch.setattr(
            "backend.services.agent.read_image.docker_cli.exec_in_container",
            fake_exec_in_container,
        )

        result = run_read_image(
            ToolContext(
                db=db,
                run_id=run["id"],
                principal_name="admin",
                principal_user_id=thread_row.owner_user_id,
                principal_is_admin=False,
            ),
            ReadImageArgs(paths=["relative.png"]),
        )
    finally:
        db.close()

    assert result.status.value == "error"
    assert result.output_json["summary"] == "read_image failed"
    assert result.output_json["details"] == "path must be absolute: relative.png"
