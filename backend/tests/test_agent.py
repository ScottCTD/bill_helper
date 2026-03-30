from __future__ import annotations

import json
import time
from pathlib import Path
from threading import Event

import pytest

from backend.database import open_session
from backend.tests.agent_test_utils import (
    build_pdf_bytes,
    collect_sse_events,
    create_thread,
    patch_model,
    send_message,
    wait_for_run_completion,
)

_MINI_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _stub_convert_upload_bundle_source(source_path: Path, *, is_pdf: bool) -> Path:
    bundle_dir = source_path.parent
    name_lower = bundle_dir.name.lower()
    if not is_pdf:
        (bundle_dir / "parsed.md").write_text(
            "# Docling (test stub)\n\nImage upload converted.\n",
            encoding="utf-8",
        )
        return bundle_dir / "parsed.md"
    lines = ["# Docling (test stub)", "", f"file: {source_path.name}", ""]
    if "statement" in name_lower:
        lines.append("Invoice total CAD 123.45")
        lines.append("Page one invoice line item")
        (bundle_dir / "statement-fig.png").write_bytes(_MINI_PNG)
        lines.append("")
        lines.append("![](statement-fig.png)")
    if "invoice" in name_lower:
        lines.extend(["Page one invoice line item", "Page two invoice line item"])
        for fname in ("p1.png", "p2.png"):
            (bundle_dir / fname).write_bytes(_MINI_PNG)
            lines.append(f"![]({fname})")
    if "scan" in name_lower:
        lines.append("OCR recovered statement total CAD 123.45")
    md = bundle_dir / "parsed.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md


@pytest.fixture(autouse=True)
def _stub_agent_docling_convert(monkeypatch):
    monkeypatch.setattr(
        "backend.services.agent.agent_attachment_bundle.convert_upload_bundle_source",
        _stub_convert_upload_bundle_source,
    )


def _patch_terminal_success(monkeypatch, *, stdout: str = "schema: name|type\ngroceries|expense") -> None:
    from backend.services.agent.tool_types import ToolExecutionResult, ToolExecutionStatus

    def fake_execute_tool(name, arguments, context):
        assert name == "terminal"
        return ToolExecutionResult(
            output_text=(
                "OK\n"
                "summary: terminal command completed\n"
                "exit_code: 0\n"
                "cwd: /workspace/scratch\n"
                "duration_ms: 1\n"
                "stdout_truncated: False\n"
                "stderr_truncated: False\n"
                f"stdout: {stdout}\n"
                "stderr: \n"
            ),
            output_json={
                "summary": "terminal command completed",
                "command": arguments["command"],
                "cwd": "/workspace/scratch",
                "exit_code": 0,
                "stdout": stdout,
                "stderr": "",
                "stdout_truncated": False,
                "stderr_truncated": False,
                "duration_ms": 1,
            },
            status=ToolExecutionStatus.OK,
        )

    monkeypatch.setattr("backend.services.agent.runtime_loop.execute_tool", fake_execute_tool)


def test_thread_history_and_final_assistant_message(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no proposals."},
    )
    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")

    assert run["status"] == "completed"
    assert run["assistant_message_id"] is not None
    assert run["change_items"] == []

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]


def test_agent_routes_are_scoped_by_principal(client, auth_headers):
    admin_thread = create_thread(client)
    response = client.get(
        "/api/v1/agent/threads",
        headers=auth_headers("alice"),
    )
    response.raise_for_status()
    assert response.json() == []

    missing_thread = client.get(
        f"/api/v1/agent/threads/{admin_thread['id']}",
        headers=auth_headers("alice"),
    )
    assert missing_thread.status_code == 404


def test_thread_detail_includes_configured_model_name(client):
    from backend.config import get_settings

    thread = create_thread(client)
    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert detail["configured_model_name"] == get_settings().agent_model


def test_send_message_allows_explicit_model_selection(client, monkeypatch):
    from backend.config import get_settings

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Selected model applied."},
    )

    settings_response = client.patch(
        "/api/v1/settings",
        json={
            "available_agent_models": [
                "bedrock/us.anthropic.claude-sonnet-4-6",
                "openai/gpt-4.1-mini",
            ]
        },
    )
    settings_response.raise_for_status()

    thread = create_thread(client)
    run = send_message(
        client,
        thread["id"],
        "Use the selected model.",
        model_name="openai/gpt-4.1-mini",
    )

    assert run["status"] == "completed"
    assert run["model_name"] == "openai/gpt-4.1-mini"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["configured_model_name"] == get_settings().agent_model
    assert detail["runs"][0]["model_name"] == "openai/gpt-4.1-mini"


def test_send_message_rejects_model_outside_available_agent_models(client):
    thread = create_thread(client)
    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={
            "content": "hello",
            "model_name": "google/gemini-2.5-pro",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Selected model is not enabled in runtime settings."


def test_run_includes_context_tokens(client, monkeypatch):
    monkeypatch.setattr(
        "backend.services.agent.runtime.calculate_context_tokens",
        lambda *, model_name, llm_messages: 321,
    )
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no proposals."},
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")

    assert run["context_tokens"] == 321

    run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_response.raise_for_status()
    assert run_response.json()["context_tokens"] == 321


def test_send_message_persists_telegram_surface_and_formats_terminal_reply(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def model(messages):
        captured_messages.append(messages)
        return {
            "role": "assistant",
            "content": "## Summary\n**Done**\n[Receipt](https://example.com/receipt)",
        }

    patch_model(monkeypatch, model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Summarize this", surface="telegram")

    assert run["status"] == "completed"
    assert run["surface"] == "telegram"
    assert run["reply_surface"] == "telegram"
    assert run["terminal_assistant_reply"] == "Summary\nDone\nReceipt (https://example.com/receipt)"
    assert captured_messages

    run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_response.raise_for_status()
    payload = run_response.json()
    assert payload["surface"] == "telegram"
    assert payload["reply_surface"] == "telegram"
    assert payload["terminal_assistant_reply"] == "Summary\nDone\nReceipt (https://example.com/receipt)"


def test_get_run_surface_override_formats_terminal_reply_for_telegram(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "**Bold** response"},
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")

    run_response = client.get(f"/api/v1/agent/runs/{run['id']}", params={"surface": "telegram"})
    run_response.raise_for_status()
    payload = run_response.json()
    assert payload["surface"] == "app"
    assert payload["reply_surface"] == "telegram"
    assert payload["terminal_assistant_reply"] == "Bold response"


def test_thread_detail_uses_persisted_context_tokens_for_idle_thread(client, monkeypatch):
    monkeypatch.setattr(
        "backend.services.agent.runtime.calculate_context_tokens",
        lambda *, model_name, llm_messages: 123,
    )
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no proposals."},
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")
    assert run["context_tokens"] == 123

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert detail["current_context_tokens"] == 123
    assert detail["runs"][0]["context_tokens"] == 123


def test_thread_detail_prefers_running_run_context_tokens(client, monkeypatch):
    proceed_second_call = Event()
    entered_second_call = Event()
    call_count = {"value": 0}

    monkeypatch.setattr(
        "backend.services.agent.runtime.calculate_context_tokens",
        lambda *, model_name, llm_messages: len(llm_messages) * 100,
    )
    def multi_step_model(_messages):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_terminal",
                        "type": "function",
                        "function": {
                            "name": "terminal",
                            "arguments": json.dumps({"command": "bh tags list"}),
                        },
                    }
                ],
            }

        entered_second_call.set()
        proceed_second_call.wait(timeout=1.0)
        return {"role": "assistant", "content": "Done"}

    patch_model(monkeypatch, multi_step_model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.", wait_for_completion=False)

    assert run["status"] == "running"
    assert entered_second_call.wait(timeout=1.0)

    run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_response.raise_for_status()
    running_payload = run_response.json()
    assert running_payload["status"] == "running"
    assert running_payload["context_tokens"] == 400

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert detail["current_context_tokens"] == 400
    assert detail["runs"][0]["context_tokens"] == 400

    proceed_second_call.set()
    payload = wait_for_run_completion(client, run["id"], timeout_seconds=1.0)
    assert payload["context_tokens"] == 400


def test_delete_thread_removes_thread_from_list_and_detail(client):
    thread = create_thread(client)

    delete_response = client.delete(f"/api/v1/agent/threads/{thread['id']}")
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/agent/threads")
    list_response.raise_for_status()
    listed_ids = [row["id"] for row in list_response.json()]
    assert thread["id"] not in listed_ids

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    assert detail_response.status_code == 404
    assert detail_response.json()["detail"] == "Thread not found"


def test_patch_thread_renames_thread(client):
    thread = create_thread(client)

    response = client.patch(
        f"/api/v1/agent/threads/{thread['id']}",
        json={"title": "Budget Review"},
    )
    response.raise_for_status()
    renamed = response.json()

    assert renamed["title"] == "Budget Review"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    assert detail_response.json()["thread"]["title"] == "Budget Review"


def test_patch_thread_rejects_titles_longer_than_five_words(client):
    thread = create_thread(client)

    response = client.patch(
        f"/api/v1/agent/threads/{thread['id']}",
        json={"title": "one two three four five six"},
    )

    assert response.status_code == 422


def test_delete_thread_rejects_running_run(client, monkeypatch):
    block_model = Event()
    block_model.clear()

    def waiting_model(_messages):
        block_model.wait(timeout=1.0)
        return {"role": "assistant", "content": "Done"}

    patch_model(monkeypatch, waiting_model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please wait", wait_for_completion=False)
    assert run["status"] == "running"

    delete_response = client.delete(f"/api/v1/agent/threads/{thread['id']}")
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"] == "Cannot delete a thread while an agent run is still running."

    block_model.set()
    final_run = wait_for_run_completion(client, run["id"])
    assert final_run["status"] != "running"


def test_uploaded_attachments_are_stored_under_canonical_user_files(client, monkeypatch):
    from backend.config import get_settings

    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Attachment processed."})

    thread = create_thread(client)
    send_message(
        client,
        thread["id"],
        "Process the receipt",
        files=[("receipt.png", b"\x89PNG\r\n\x1a\n", "image/png")],
    )

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    attachment_paths = [
        Path(attachment["file_path"])
        for message in detail["messages"]
        for attachment in message["attachments"]
    ]

    assert attachment_paths
    expected_root = get_settings().data_dir / "user_files"
    assert all(expected_root in path.parents for path in attachment_paths)
    assert all(path.exists() for path in attachment_paths)


def test_draft_attachment_upload_can_be_sent_later_by_attachment_id(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed uploaded draft attachment."}

    patch_model(monkeypatch, capture_model)

    upload_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("statement.pdf", build_pdf_bytes(["Invoice total CAD 123.45"]), "application/pdf")},
    )
    upload_response.raise_for_status()
    draft_attachment = upload_response.json()

    thread = create_thread(client)
    run = send_message(
        client,
        thread["id"],
        "Please summarize this attachment.",
        attachment_ids=[draft_attachment["id"]],
    )

    assert run["status"] == "completed"
    assert captured_messages

    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert [part.get("type") for part in user_content] == ["text", "text"]
    assert "statement.pdf" in user_content[0].get("text", "")
    assert user_content[1].get("text") == "Please summarize this attachment."

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    first_user = next(message for message in detail["messages"] if message["role"] == "user")
    assert len(first_user["attachments"]) == 1
    assert first_user["attachments"][0]["display_name"] == "statement.pdf"


def test_draft_attachment_upload_reuses_parsed_bundle_for_same_hash(client, monkeypatch):
    from backend.models_files import UserFile
    from backend.services.user_files import resolve_user_file_path

    convert_calls: list[Path] = []

    def stub_convert(source_path: Path, *, is_pdf: bool) -> Path:
        convert_calls.append(source_path)
        bundle_dir = source_path.parent
        (bundle_dir / "parsed.md").write_text("# reused bundle\n", encoding="utf-8")
        return bundle_dir / "parsed.md"

    monkeypatch.setattr(
        "backend.services.agent.agent_attachment_bundle.convert_upload_bundle_source",
        stub_convert,
    )

    pdf_bytes = build_pdf_bytes(["Invoice total CAD 123.45"])
    first_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    first_response.raise_for_status()
    first_attachment = first_response.json()

    second_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    second_response.raise_for_status()
    second_attachment = second_response.json()

    assert len(convert_calls) == 1
    assert first_attachment["id"] != second_attachment["id"]

    with open_session() as db:
        first_user_file = db.get(UserFile, first_attachment["id"])
        second_user_file = db.get(UserFile, second_attachment["id"])
        assert first_user_file is not None
        assert second_user_file is not None
        assert first_user_file.stored_relative_path != second_user_file.stored_relative_path
        assert first_user_file.sha256 == second_user_file.sha256
        assert resolve_user_file_path(first_user_file).parent.joinpath("parsed.md").is_file()
        assert resolve_user_file_path(second_user_file).parent.joinpath("parsed.md").is_file()


def test_draft_attachment_upload_reruns_docling_when_hash_match_bundle_lacks_parsed_markdown(client, monkeypatch):
    from backend.models_files import UserFile
    from backend.services.user_files import resolve_user_file_path

    convert_calls: list[Path] = []

    def stub_convert(source_path: Path, *, is_pdf: bool) -> Path:
        convert_calls.append(source_path)
        bundle_dir = source_path.parent
        (bundle_dir / "parsed.md").write_text("# regenerated bundle\n", encoding="utf-8")
        return bundle_dir / "parsed.md"

    monkeypatch.setattr(
        "backend.services.agent.agent_attachment_bundle.convert_upload_bundle_source",
        stub_convert,
    )

    pdf_bytes = build_pdf_bytes(["Invoice total CAD 123.45"])
    first_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    first_response.raise_for_status()
    first_attachment = first_response.json()

    with open_session() as db:
        first_user_file = db.get(UserFile, first_attachment["id"])
        assert first_user_file is not None
        resolve_user_file_path(first_user_file).parent.joinpath("parsed.md").unlink()

    second_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    second_response.raise_for_status()
    second_attachment = second_response.json()

    assert len(convert_calls) == 2

    with open_session() as db:
        second_user_file = db.get(UserFile, second_attachment["id"])
        assert second_user_file is not None
        assert resolve_user_file_path(second_user_file).parent.joinpath("parsed.md").is_file()


def test_draft_attachment_upload_without_ocr_for_pdf_skips_docling_markdown_and_keeps_page_images(client, monkeypatch):
    from backend.models_files import UserFile
    from backend.services.user_files import resolve_user_file_path

    convert_calls: list[Path] = []

    def stub_convert(source_path: Path, *, is_pdf: bool) -> Path:
        convert_calls.append(source_path)
        bundle_dir = source_path.parent
        (bundle_dir / "parsed.md").write_text("# should not exist\n", encoding="utf-8")
        return bundle_dir / "parsed.md"

    monkeypatch.setattr(
        "backend.services.agent.agent_attachment_bundle.convert_upload_bundle_source",
        stub_convert,
    )

    pdf_bytes = build_pdf_bytes(["Invoice total CAD 123.45"])
    response = client.post(
        "/api/v1/agent/draft-attachments",
        data={"use_ocr": "false"},
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    response.raise_for_status()
    attachment = response.json()

    assert convert_calls == []

    with open_session() as db:
        user_file = db.get(UserFile, attachment["id"])
        assert user_file is not None
        bundle_dir = resolve_user_file_path(user_file).parent
        assert not bundle_dir.joinpath("parsed.md").exists()
        assert bundle_dir.joinpath("page-1.png").is_file()


def test_draft_attachment_upload_runs_docling_when_ocr_is_enabled_after_raw_duplicate(client, monkeypatch):
    convert_calls: list[Path] = []

    def stub_convert(source_path: Path, *, is_pdf: bool) -> Path:
        convert_calls.append(source_path)
        bundle_dir = source_path.parent
        (bundle_dir / "parsed.md").write_text("# regenerated with ocr\n", encoding="utf-8")
        return bundle_dir / "parsed.md"

    monkeypatch.setattr(
        "backend.services.agent.agent_attachment_bundle.convert_upload_bundle_source",
        stub_convert,
    )

    pdf_bytes = build_pdf_bytes(["Invoice total CAD 123.45"])
    first_response = client.post(
        "/api/v1/agent/draft-attachments",
        data={"use_ocr": "false"},
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    first_response.raise_for_status()

    second_response = client.post(
        "/api/v1/agent/draft-attachments",
        data={"use_ocr": "true"},
        files={"file": ("statement.pdf", pdf_bytes, "application/pdf")},
    )
    second_response.raise_for_status()

    assert len(convert_calls) == 1


def test_delete_draft_attachment_removes_unbound_upload_bundle(client):
    from backend.models_files import UserFile
    from backend.services.user_files import resolve_user_file_path

    upload_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("receipt.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    upload_response.raise_for_status()
    draft_attachment = upload_response.json()

    with open_session() as db:
        user_file = db.get(UserFile, draft_attachment["id"])
        assert user_file is not None
        bundle_dir = resolve_user_file_path(user_file).parent
        assert bundle_dir.exists()

    delete_response = client.delete(f"/api/v1/agent/draft-attachments/{draft_attachment['id']}")
    assert delete_response.status_code == 204

    with open_session() as db:
        assert db.get(UserFile, draft_attachment["id"]) is None
    assert not bundle_dir.exists()


def test_delete_draft_attachment_rejects_bound_message_attachment(client, monkeypatch):
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Attachment processed."})

    upload_response = client.post(
        "/api/v1/agent/draft-attachments",
        files={"file": ("receipt.png", b"\x89PNG\r\n\x1a\n", "image/png")},
    )
    upload_response.raise_for_status()
    draft_attachment = upload_response.json()

    thread = create_thread(client)
    run = send_message(
        client,
        thread["id"],
        "Process this receipt.",
        attachment_ids=[draft_attachment["id"]],
    )
    assert run["status"] == "completed"

    delete_response = client.delete(f"/api/v1/agent/draft-attachments/{draft_attachment['id']}")
    assert delete_response.status_code == 409
    assert delete_response.json()["detail"] == "Attachment is already bound to a message and cannot be removed."


def test_thread_list_marks_running_threads(client, monkeypatch):
    block_model = Event()
    block_model.clear()

    def waiting_model(_messages):
        block_model.wait(timeout=1.0)
        return {"role": "assistant", "content": "Done"}

    patch_model(monkeypatch, waiting_model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please wait", wait_for_completion=False)
    assert run["status"] == "running"

    list_response = client.get("/api/v1/agent/threads")
    list_response.raise_for_status()
    listed_row = next(row for row in list_response.json() if row["id"] == thread["id"])
    assert listed_row["has_running_run"] is True

    block_model.set()
    wait_for_run_completion(client, run["id"])

    list_response = client.get("/api/v1/agent/threads")
    list_response.raise_for_status()
    listed_row = next(row for row in list_response.json() if row["id"] == thread["id"])
    assert listed_row["has_running_run"] is False


def test_delete_thread_keeps_canonical_uploaded_attachment_files(client, monkeypatch):
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Attachment processed."})

    thread = create_thread(client)
    send_message(
        client,
        thread["id"],
        "Process the receipt",
        files=[("receipt.png", b"\x89PNG\r\n\x1a\n", "image/png")],
    )

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    attachment_paths = [
        Path(attachment["file_path"])
        for message in detail["messages"]
        for attachment in message["attachments"]
    ]
    assert attachment_paths
    assert all(path.exists() for path in attachment_paths)

    delete_response = client.delete(f"/api/v1/agent/threads/{thread['id']}")
    assert delete_response.status_code == 204
    assert all(path.exists() for path in attachment_paths)


def test_default_agent_model_matches_config_default():
    from backend.config import DEFAULT_AGENT_MODEL, get_settings

    assert get_settings().agent_model == DEFAULT_AGENT_MODEL


def test_model_supports_vision_has_manual_override_for_openrouter_qwen_qwen3_5_27b(monkeypatch):
    from backend.services.agent import attachment_content

    monkeypatch.setattr(attachment_content.litellm, "supports_vision", lambda _model: False)

    assert attachment_content.model_supports_vision("openrouter/qwen/qwen3.5-27b") is True
    assert attachment_content.model_supports_vision("qwen/qwen3.5-27b") is True


def test_pdf_line_normalization_collapses_internal_whitespace_and_trims_edges():
    from backend.services.agent.attachment_content import normalize_pdf_text_lines

    normalized = normalize_pdf_text_lines("  Invoice   total\tCAD  123.45  \n\n  Line   2  ")
    assert normalized == "Invoice total CAD 123.45\n\nLine 2"


def test_send_message_rejects_unsupported_attachment_type(client):
    thread = create_thread(client)
    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={"content": "process this"},
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only image and PDF attachments are supported."


def test_image_attachment_can_skip_ocr_for_vision_model(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed image visually."}

    patch_model(monkeypatch, capture_model)
    settings_response = client.patch(
        "/api/v1/settings",
        json={
            "available_agent_models": [
                "openrouter/qwen/qwen3.5-27b",
                "gpt-test",
            ]
        },
    )
    settings_response.raise_for_status()

    thread = create_thread(client)
    run = send_message(
        client,
        thread["id"],
        "Describe this image.",
        files=[("receipt.png", _MINI_PNG, "image/png")],
        attachments_use_ocr=False,
        model_name="openrouter/qwen/qwen3.5-27b",
    )

    assert run["status"] == "completed"
    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert [part.get("type") for part in user_content] == ["text", "image_url", "text"]
    assert "receipt.png" in user_content[0].get("text", "")
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert user_content[2].get("text") == "Describe this image."


def test_pdf_attachment_can_skip_ocr_for_vision_model(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed PDF visually."}

    patch_model(monkeypatch, capture_model)
    settings_response = client.patch(
        "/api/v1/settings",
        json={
            "available_agent_models": [
                "openrouter/qwen/qwen3.5-27b",
                "gpt-test",
            ]
        },
    )
    settings_response.raise_for_status()

    thread = create_thread(client)
    pdf_bytes = build_pdf_bytes(
        [
            "Page one invoice line item",
            "Page two invoice line item",
        ]
    )
    run = send_message(
        client,
        thread["id"],
        "Read this PDF visually.",
        files=[("invoice.pdf", pdf_bytes, "application/pdf")],
        attachments_use_ocr=False,
        model_name="openrouter/qwen/qwen3.5-27b",
    )

    assert run["status"] == "completed"
    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert user_content[0].get("type") == "text"
    assert "invoice.pdf" in user_content[0].get("text", "")
    image_parts = [part for part in user_content if isinstance(part, dict) and part.get("type") == "image_url"]
    assert len(image_parts) == 2
    assert all(part["image_url"]["url"].startswith("data:image/png;base64,") for part in image_parts)
    assert user_content[-1].get("text") == "Read this PDF visually."


def test_send_message_rejects_disabling_ocr_for_non_vision_model(client, monkeypatch):
    monkeypatch.setattr("backend.services.agent.execution.model_supports_vision", lambda _model_name: False)
    settings_response = client.patch(
        "/api/v1/settings",
        json={
            "available_agent_models": [
                "gpt-test",
                "openai/gpt-4.1-mini",
            ]
        },
    )
    settings_response.raise_for_status()

    thread = create_thread(client)
    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={
            "content": "Describe this image.",
            "attachments_use_ocr": "false",
            "model_name": "gpt-test",
        },
        files=[("files", ("receipt.png", _MINI_PNG, "image/png"))],
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "OCR can only be disabled when the selected model supports vision."


def test_pdf_attachment_includes_docling_markdown_without_eager_images(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed PDF text."}

    patch_model(monkeypatch, capture_model)

    thread = create_thread(client)
    pdf_bytes = build_pdf_bytes(["Invoice total CAD 123.45"])
    run = send_message(
        client,
        thread["id"],
        "Please summarize this attachment.",
        files=[("statement.pdf", pdf_bytes, "application/pdf")],
    )

    assert run["status"] == "completed"
    assert captured_messages

    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert [part.get("type") for part in user_content] == ["text", "text"]
    first_text = user_content[0].get("text", "")
    assert "statement.pdf" in first_text
    assert "Docling" in first_text or "parsed.md" in first_text
    assert "Invoice total CAD" in first_text
    assert user_content[1].get("text") == "Please summarize this attachment."

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    first_user = next(message for message in detail["messages"] if message["role"] == "user")
    assert len(first_user["attachments"]) == 1
    assert first_user["attachments"][0]["mime_type"] == "application/pdf"


def test_pdf_attachment_lists_docling_figure_images_without_eager_image_parts(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed PDF pages."}

    patch_model(monkeypatch, capture_model)

    thread = create_thread(client)
    pdf_bytes = build_pdf_bytes(
        [
            "Page one invoice line item",
            "Page two invoice line item",
        ]
    )
    run = send_message(
        client,
        thread["id"],
        "Read every page.",
        files=[("invoice.pdf", pdf_bytes, "application/pdf")],
    )

    assert run["status"] == "completed"
    assert captured_messages

    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert [part.get("type") for part in user_content] == ["text", "text"]
    head = user_content[0].get("text", "")
    assert "invoice.pdf" in head
    assert "Page one invoice line item" in head
    assert "Page two invoice line item" in head
    assert "Use `read_image`" in head
    assert "/workspace/uploads/" in head
    assert ".png" in head
    assert user_content[-1].get("text") == "Read every page."


def test_attachment_parts_stay_before_user_prompt_for_mixed_uploads(client, monkeypatch):
    captured_messages: list[list[dict]] = []

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed mixed attachments."}

    patch_model(monkeypatch, capture_model)

    thread = create_thread(client)
    pdf_bytes = build_pdf_bytes(["Page one invoice line item"])
    run = send_message(
        client,
        thread["id"],
        "Compare both files.",
        files=[
            ("statement.pdf", pdf_bytes, "application/pdf"),
            ("receipt.png", b"\x89PNG\r\n\x1a\n", "image/png"),
        ],
    )

    assert run["status"] == "completed"
    assert captured_messages

    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert [part.get("type") for part in user_content] == ["text", "text", "text"]
    assert "statement.pdf" in user_content[0].get("text", "")
    assert "Use `read_image`" in user_content[0].get("text", "")
    assert "receipt.png" in user_content[1].get("text", "")
    assert "parsed.md" in user_content[1].get("text", "")
    assert "Use `read_image`" in user_content[1].get("text", "")
    assert user_content[2].get("text") == "Compare both files."


def test_system_prompt_includes_current_date_tag():
    from datetime import date

    from backend.services.agent.prompts import SystemPromptContext, system_prompt

    prompt = system_prompt(SystemPromptContext(current_date=date(2026, 2, 10)))
    assert "## Current User Context" in prompt
    assert "- User Timezone: America/Toronto" in prompt
    assert "- Current date: 2026-02-10" in prompt


def test_system_prompt_renders_jinja_template_without_leaking_placeholders():
    from datetime import date
    from importlib.resources import files

    from backend.services.agent.prompts import (
        SYSTEM_PROMPT_TEMPLATE_NAME,
        SystemPromptContext,
        system_prompt,
    )

    template_path = files("backend.services.agent").joinpath(SYSTEM_PROMPT_TEMPLATE_NAME)
    template_text = template_path.read_text(encoding="utf-8")

    prompt = system_prompt(
        SystemPromptContext(
            current_date=date(2026, 2, 10),
            current_timezone="America/Vancouver",
            current_user_context="Primary checking",
        )
    )

    assert template_path.name == "system_prompt.j2"
    assert "## Identity" in template_text
    assert "{{ timezone_name }}" in template_text
    assert "{{" not in prompt
    assert "{%" not in prompt
    assert "Primary checking" in prompt
    assert "## Current User Context" in prompt
    assert "- User Timezone: America/Vancouver" in prompt
    assert "- Current date: 2026-02-10" in prompt


def test_system_prompt_adds_telegram_surface_guidance():
    from backend.services.agent.prompts import SystemPromptContext, system_prompt

    prompt = system_prompt(SystemPromptContext(response_surface="telegram"))

    assert "### Response Surface" in prompt
    assert "telegram" in prompt
    assert "Avoid Markdown-heavy formatting, tables, and fenced code blocks." in prompt


def test_system_prompt_includes_user_memory_when_present():
    from backend.services.agent.prompts import SystemPromptContext, system_prompt

    prompt = system_prompt(
        SystemPromptContext(
            user_memory=["Prefers terse answers.", "Always mention CAD explicitly."],
        )
    )

    assert "### Agent Memory" in prompt
    assert "- Prefers terse answers." in prompt
    assert "- Always mention CAD explicitly." in prompt
    assert "persistent user-provided background and preferences" in prompt


def test_system_prompt_uses_requested_current_timezone_for_date_label():
    from datetime import date

    from backend.services.agent.prompts import SystemPromptContext, system_prompt

    prompt = system_prompt(
        SystemPromptContext(
            current_date=date(2026, 2, 10),
            current_timezone="America/Vancouver",
        )
    )
    assert "- User Timezone: America/Vancouver" in prompt
    assert "- Current date: 2026-02-10" in prompt


def test_system_prompt_falls_back_to_toronto_for_invalid_timezone():
    from datetime import date

    from backend.services.agent.prompts import SystemPromptContext, system_prompt

    prompt = system_prompt(
        SystemPromptContext(
            current_date=date(2026, 2, 10),
            current_timezone="Not/AZone",
        )
    )
    assert "- User Timezone: America/Toronto" in prompt
    assert "- Current date: 2026-02-10" in prompt


def test_system_prompt_includes_current_user_account_context(client, monkeypatch):
    create_account_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Main Checking",
            "markdown_body": "## Checking notes\n- reconcile every Friday",
            "currency_code": "usd",
            "is_active": True,
        },
    )
    create_account_response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "ok"}

    patch_model(monkeypatch, model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")
    assert run["status"] == "completed"
    assert captured_messages

    system_message = captured_messages[-1][0]
    assert system_message.get("role") == "system"
    system_content = str(system_message.get("content", ""))
    assert "## Current User Context" in system_content
    assert "- User Timezone: America/Toronto" in system_content
    assert "- Current date:" in system_content
    assert "accounts_count: 1" in system_content
    assert "name=Main Checking" in system_content
    assert "currency=USD" in system_content
    assert "notes_markdown:" in system_content
    assert "## Checking notes" in system_content
    assert "- reconcile every Friday" in system_content


def test_system_prompt_includes_entity_category_reference_context(client, monkeypatch):
    create_term_response = client.post(
        "/api/v1/taxonomies/entity_category/terms",
        json={
            "name": "service_provider",
            "description": "Recurring vendors and contractors that provide ongoing services.",
        },
    )
    create_term_response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "ok"}

    patch_model(monkeypatch, model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")
    assert run["status"] == "completed"
    assert captured_messages

    system_message = captured_messages[-1][0]
    system_content = str(system_message.get("content", ""))
    assert "### Entity Category Reference" in system_content
    assert "- service_provider: Recurring vendors and contractors that provide ongoing services." in system_content


def test_system_prompt_truncates_account_markdown_image_data_urls(client, monkeypatch):
    huge_data_url = "data:image/png;base64," + ("a" * 300)
    create_account_response = client.post(
        "/api/v1/accounts",
        json={
            "name": "Travel Card",
            "markdown_body": f"![statement]({huge_data_url})",
            "currency_code": "usd",
            "is_active": True,
        },
    )
    create_account_response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "ok"}

    patch_model(monkeypatch, model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")
    assert run["status"] == "completed"
    assert captured_messages

    system_message = captured_messages[-1][0]
    assert system_message.get("role") == "system"
    system_content = str(system_message.get("content", ""))
    assert "![statement](data:image/png;base64," in system_content
    assert "...(truncated)" in system_content
    assert huge_data_url not in system_content


def test_settings_user_memory_is_injected_into_system_prompt(client, monkeypatch):
    response = client.patch(
        "/api/v1/settings",
        json={"user_memory": ["Prefers terse answers.", "Works in CAD."]},
    )
    response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "ok"}

    patch_model(monkeypatch, model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")
    assert run["status"] == "completed"
    assert captured_messages

    system_message = captured_messages[-1][0]
    system_content = str(system_message.get("content", ""))
    assert "### Agent Memory" in system_content
    assert "- Prefers terse answers." in system_content
    assert "- Works in CAD." in system_content


def test_tool_catalog_exposes_only_terminal_and_retained_session_tools():
    from backend.services.agent.tools import build_openai_tool_schemas

    names = [tool["function"]["name"] for tool in build_openai_tool_schemas()]
    assert "search_entries" not in names
    assert "add_user_memory" in names
    assert "rename_thread" in names
    assert "send_intermediate_update" in names
    assert "terminal" in names
    assert "read_image" in names
    assert names == [
        "add_user_memory",
        "rename_thread",
        "send_intermediate_update",
        "terminal",
        "read_image",
    ]


def test_execute_tool_returns_json_safe_validation_errors_for_rename_thread() -> None:
    from backend.services.agent.tool_runtime_support.execution import execute_tool
    from backend.services.agent.tool_types import ToolContext

    with open_session() as db:
        result = execute_tool(
            "rename_thread",
            {"title": "one two three four"},
            ToolContext(db=db, run_id="run-1"),
        )

    assert result.status == "error"
    assert result.output_json["summary"] == "invalid tool arguments"
    details = result.output_json["details"]
    assert isinstance(details, list)
    assert details
    assert details[0]["type"] == "value_error"
    assert details[0]["loc"] == ("title",)
    assert "ctx" not in details[0]


def test_add_user_memory_tool_persists_runtime_settings_memory(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "I'll remember that."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_add_user_memory",
                    "type": "function",
                    "function": {
                        "name": "add_user_memory",
                        "arguments": json.dumps(
                            {
                                "memory_items": [
                                    "Prefers terse answers.",
                                    "Works in CAD.",
                                ]
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Remember that I prefer terse answers and work in CAD.")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "add_user_memory"
    assert run["tool_calls"][0]["display_label"] == "Added 2 memory items"
    assert run["tool_calls"][0]["output_json"]["added_items"] == [
        "Prefers terse answers.",
        "Works in CAD.",
    ]

    settings_response = client.get("/api/v1/settings")
    settings_response.raise_for_status()
    assert settings_response.json()["user_memory"] == [
        "Prefers terse answers.",
        "Works in CAD.",
    ]


def test_rename_thread_tool_persists_thread_title(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_rename_thread",
                    "type": "function",
                    "function": {
                        "name": "rename_thread",
                        "arguments": json.dumps({"title": "Budget Review"}),
                    },
                }
            ],
        },
        {"role": "assistant", "content": "Done."},
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please summarize my budget.")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "rename_thread"
    assert run["tool_calls"][0]["output_json"]["title"] == "Budget Review"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    assert detail_response.json()["thread"]["title"] == "Budget Review"


def test_untitled_thread_restricts_model_request_to_rename_thread(client, monkeypatch):
    from backend.services.agent import runtime

    captured_kwargs: list[dict[str, object]] = []
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_rename_thread",
                    "type": "function",
                    "function": {
                        "name": "rename_thread",
                        "arguments": json.dumps({"title": "Budget Review"}),
                    },
                }
            ],
        },
        {"role": "assistant", "content": "Done."},
    ]

    def fake_model(_messages, _db, **kwargs):
        captured_kwargs.append(kwargs)
        return calls.pop(0)

    monkeypatch.setattr(runtime, "call_model", fake_model)

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please summarize my budget.")

    assert run["status"] == "completed"
    assert captured_kwargs
    assert captured_kwargs[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "rename_thread"},
    }
    assert [tool["function"]["name"] for tool in captured_kwargs[0]["tools"]] == [
        "rename_thread"
    ]


def test_openrouter_qwen_untitled_thread_still_requests_explicit_tool_choice(client, monkeypatch):
    from backend.services.agent import runtime

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    captured_kwargs: list[dict[str, object]] = []
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_rename_thread",
                    "type": "function",
                    "function": {
                        "name": "rename_thread",
                        "arguments": json.dumps({"title": "Budget Review"}),
                    },
                }
            ],
        },
        {"role": "assistant", "content": "Done."},
    ]

    def fake_model(_messages, _db, **kwargs):
        captured_kwargs.append(kwargs)
        return calls.pop(0)

    monkeypatch.setattr(runtime, "call_model", fake_model)

    thread = create_thread(client)
    run = send_message(
        client,
        thread["id"],
        "Please summarize my budget.",
        model_name="openrouter/qwen/qwen3.5-27b",
    )

    assert run["status"] == "completed"
    assert captured_kwargs
    assert captured_kwargs[0]["tool_choice"] == {
        "type": "function",
        "function": {"name": "rename_thread"},
    }
    assert [tool["function"]["name"] for tool in captured_kwargs[0]["tools"]] == [
        "rename_thread"
    ]


def test_thread_title_stays_untitled_without_rename_tool(client, monkeypatch):
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "No rename."})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")

    assert run["status"] == "completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    assert detail_response.json()["thread"]["title"] is None


def test_system_prompt_embeds_bh_cheat_sheet_only():
    from backend.cli.reference import render_bh_cheat_sheet
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()

    assert "## `bh` Reference" in prompt
    assert render_bh_cheat_sheet() in prompt
    assert "billengine" not in prompt.lower()


def test_agent_feature_doc_embeds_generated_runtime_tool_and_bh_sections():
    from backend.cli.reference import render_bh_cheat_sheet
    from backend.services.agent.tool_reference import render_runtime_tool_contract_markdown

    doc_path = Path("docs/features/agent_billing_assistant.md")
    document = doc_path.read_text(encoding="utf-8")

    runtime_start = "<!-- GENERATED:runtime-tool-contracts:start -->"
    runtime_end = "<!-- GENERATED:runtime-tool-contracts:end -->"
    bh_start = "<!-- GENERATED:bh-cheat-sheet:start -->"
    bh_end = "<!-- GENERATED:bh-cheat-sheet:end -->"

    runtime_block = document.split(runtime_start, maxsplit=1)[1].split(runtime_end, maxsplit=1)[0].strip()
    bh_block = document.split(bh_start, maxsplit=1)[1].split(bh_end, maxsplit=1)[0].strip()

    assert runtime_block == render_runtime_tool_contract_markdown().strip()
    assert bh_block == render_bh_cheat_sheet().strip()
    assert "billengine" not in document.lower()


def test_run_persists_tool_calls(client, monkeypatch):
    _patch_terminal_success(monkeypatch)
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "arguments": json.dumps({"command": "bh tags list"}),
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "I checked tags and found no pending proposals.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "terminal"
    assert run["tool_calls"][0]["status"] == "ok"
    assert isinstance(run["tool_calls"][0]["output_text"], str)
    assert run["tool_calls"][0]["output_text"].startswith("OK")

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    payload = run_detail.json()
    assert payload["assistant_message_id"] == run["assistant_message_id"]
    assert len(payload["tool_calls"]) == 1


def test_run_records_tool_argument_decode_failures(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {"name": "terminal", "arguments": "{"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": "I could not decode the first tool call arguments.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    tool_call = run["tool_calls"][0]
    assert tool_call["tool_name"] == "terminal"
    assert tool_call["display_label"] == "Ran terminal command"
    assert tool_call["status"] == "error"
    assert tool_call["input_json"] == {}
    assert tool_call["output_json"]["summary"] == "tool argument decode failed"
    assert tool_call["output_json"]["details"]["decode_error"] == "arguments are not valid JSON"
    assert tool_call["output_json"]["details"]["raw_arguments"] == "{"


def test_thread_detail_compacts_tool_call_payloads(client, monkeypatch):
    _patch_terminal_success(monkeypatch)
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "arguments": json.dumps({"command": "bh tags list"}),
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "Done.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert len(detail["runs"]) == 1
    compact_tool_call = detail["runs"][0]["tool_calls"][0]
    assert compact_tool_call["id"] == run["tool_calls"][0]["id"]
    assert compact_tool_call["tool_name"] == "terminal"
    assert compact_tool_call["display_label"] == "bh tags list"
    assert compact_tool_call["has_full_payload"] is False
    assert compact_tool_call["input_json"] is None
    assert compact_tool_call["output_json"] is None
    assert compact_tool_call["output_text"] is None


def test_tool_call_detail_endpoint_returns_full_payload(client, monkeypatch):
    _patch_terminal_success(monkeypatch)
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "arguments": json.dumps({"command": "bh tags list"}),
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "Done.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")
    tool_call_id = run["tool_calls"][0]["id"]

    response = client.get(f"/api/v1/agent/tool-calls/{tool_call_id}")
    response.raise_for_status()
    payload = response.json()

    assert payload["id"] == tool_call_id
    assert payload["tool_name"] == "terminal"
    assert payload["display_label"] == "bh tags list"
    assert payload["has_full_payload"] is True
    assert isinstance(payload["input_json"], dict)
    assert isinstance(payload["output_json"], dict)
    assert isinstance(payload["output_text"], str)

def test_run_persists_assistant_tool_step_text_as_intermediate_update(client, monkeypatch):
    _patch_terminal_success(monkeypatch)
    calls = [
        {
            "role": "assistant",
            "content": "I am checking current tags before making any changes.",
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "arguments": json.dumps({"command": "bh tags list"}),
                    },
                }
            ],
        },
        {
            "role": "assistant",
            "content": "I checked tags and found no pending proposals.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "terminal"
    reasoning_events = [event for event in run["events"] if event["event_type"] == "reasoning_update"]
    assert len(reasoning_events) == 1
    assert reasoning_events[0]["message"] == "I am checking current tags before making any changes."
    assert reasoning_events[0]["source"] == "assistant_content"


def test_final_message_strips_empty_pending_review_footer(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {
            "role": "assistant",
            "content": (
                "Here is your dashboard summary.\n\n"
                "Tools used (high level): terminal (checked bh entries list) "
                "Pending review item ids: []"
            ),
        },
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Show dashboard")
    assert run["status"] == "completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assistant_content = assistant_messages[0]["content_markdown"]
    assert "Pending review item ids: []" not in assistant_content
    assert "Tools used (high level):" not in assistant_content


def test_send_message_returns_running_while_agent_executes(client, monkeypatch):
    entered_model = Event()
    release_model = Event()

    def slow_model(_messages):
        entered_model.set()
        release_model.wait(timeout=1.0)
        return {"role": "assistant", "content": "Done."}

    patch_model(monkeypatch, slow_model)
    thread = create_thread(client)

    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={"content": "hello"},
    )
    response.raise_for_status()
    run = response.json()

    assert run["status"] == "running"
    assert run["assistant_message_id"] is None
    assert entered_model.wait(timeout=1.0)

    release_model.set()
    payload = wait_for_run_completion(client, run["id"], timeout_seconds=2.0)
    assert payload["status"] == "completed"
    assert payload["assistant_message_id"] is not None


def test_stream_message_endpoint_emits_real_time_events(client, monkeypatch):
    from backend.services.agent import runtime

    def stream_model(_messages, _db, **_kwargs):
        yield {"type": "text_delta", "delta": "Hel"}
        yield {"type": "text_delta", "delta": "lo"}
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": "Hello",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                },
            },
        }

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "say hello")

    assert events
    run_events = [event for event in events if event.get("type") == "run_event"]
    run_event_types = [event["event"]["event_type"] for event in run_events]
    assert run_event_types[0] == "run_started"
    assert all("tool_call" not in event for event in run_events)
    text = "".join(event.get("delta", "") for event in events if event.get("type") == "text_delta")
    assert text == "Hello"
    assert run_event_types[-1] == "run_completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["content_markdown"] == "Hello"


def test_stream_message_allows_explicit_model_selection(client, monkeypatch):
    from backend.config import get_settings
    from backend.services.agent import runtime

    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    def stream_model(_messages, _db, **_kwargs):
        yield {"type": "text_delta", "delta": "Selected model applied."}
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": "Selected model applied.",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                },
            },
        }

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    settings_response = client.patch(
        "/api/v1/settings",
        json={
            "available_agent_models": [
                "bedrock/us.anthropic.claude-sonnet-4-6",
                "openai/gpt-4.1-mini",
            ]
        },
    )
    settings_response.raise_for_status()

    thread = create_thread(client)
    events = collect_sse_events(
        client,
        thread["id"],
        "Use the selected stream model.",
        model_name="openai/gpt-4.1-mini",
    )

    assert any(
        event.get("type") == "run_event"
        and event.get("event", {}).get("event_type") == "run_completed"
        for event in events
    )

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert detail["configured_model_name"] == get_settings().agent_model
    assert detail["runs"][0]["status"] == "completed"
    assert detail["runs"][0]["model_name"] == "openai/gpt-4.1-mini"


def test_stream_message_endpoint_persists_telegram_surface(client, monkeypatch):
    from backend.services.agent import runtime

    def stream_model(_messages, _db, **_kwargs):
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": "**Hello** from stream",
                "tool_calls": [],
            },
        }

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "say hello", surface="telegram")
    run_id = next(event["run_id"] for event in events if event.get("type") == "run_event")

    run_response = client.get(f"/api/v1/agent/runs/{run_id}")
    run_response.raise_for_status()
    payload = run_response.json()
    assert payload["surface"] == "telegram"
    assert payload["terminal_assistant_reply"] == "Hello from stream"


def test_stream_rename_thread_tool_updates_title_before_final_assistant_turn(client, monkeypatch):
    from backend.models_agent import AgentThread
    from backend.services.agent import runtime

    call_count = 0

    def stream_model(messages, db, **_kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield {
                "type": "done",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_rename_thread",
                            "type": "function",
                            "function": {
                                "name": "rename_thread",
                                "arguments": json.dumps({"title": "Budget Review"}),
                            },
                        }
                    ],
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 5,
                        "cache_read_tokens": 0,
                        "cache_write_tokens": 0,
                    },
                },
            }
            return

        thread = db.get(AgentThread, thread_id)
        assert thread is not None
        assert thread.title == "Budget Review"
        yield {"type": "text_delta", "delta": "Done."}
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": "Done.",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                },
            },
        }

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    thread = create_thread(client)
    thread_id = thread["id"]
    events = collect_sse_events(client, thread_id, "Please rename this thread")

    tool_call_events = [
        event
        for event in events
        if event.get("type") == "run_event" and event.get("event", {}).get("event_type", "").startswith("tool_call_")
    ]
    assert [event["event"]["event_type"] for event in tool_call_events] == [
        "tool_call_queued",
        "tool_call_started",
        "tool_call_completed",
    ]
    assert tool_call_events[-1]["tool_call"]["tool_name"] == "rename_thread"
    assert tool_call_events[-1]["tool_call"]["display_label"] == 'Renamed thread to "Budget Review"'
    assert events[-1]["event"]["event_type"] == "run_completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread_id}")
    detail_response.raise_for_status()
    assert detail_response.json()["thread"]["title"] == "Budget Review"


def test_stream_message_endpoint_emits_reasoning_delta_events(client, monkeypatch):
    from backend.services.agent import runtime

    def stream_model(_messages, _db, **_kwargs):
        yield {"type": "reasoning_delta", "delta": "Checking "}
        yield {"type": "reasoning_delta", "delta": "entities"}
        yield {"type": "text_delta", "delta": "Done."}
        yield {
            "type": "done",
            "message": {
                "role": "assistant",
                "content": "Done.",
                "reasoning": "Checking entities",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                },
            },
        }

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "say hello")

    reasoning_deltas = [event["delta"] for event in events if event.get("type") == "reasoning_delta"]
    assert reasoning_deltas == ["Checking ", "entities"]

    reasoning_updates = [
        event["event"]
        for event in events
        if event.get("type") == "run_event"
        and event.get("event", {}).get("event_type") == "reasoning_update"
        and event.get("event", {}).get("source") == "model_reasoning"
    ]
    assert len(reasoning_updates) == 1
    assert reasoning_updates[0]["message"] == "Checking entities"


def test_stream_message_endpoint_emits_reasoning_update_events(client, monkeypatch):
    from backend.services.agent import runtime

    stream_responses = [
        [
            {
                "type": "done",
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_intermediate_update",
                            "type": "function",
                            "function": {
                                "name": "send_intermediate_update",
                                "arguments": json.dumps({"message": "I am checking existing entries and tags."}),
                            },
                        }
                    ],
                },
            }
        ],
        [
            {
                "type": "done",
                "message": {
                    "role": "assistant",
                    "content": "Finished and ready for review.",
                    "tool_calls": [],
                },
            }
        ],
    ]

    def stream_model(_messages, _db, **_kwargs):
        for event in stream_responses.pop(0):
            yield event

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "process this import")

    reasoning_updates = [
        event["event"]
        for event in events
        if event.get("type") == "run_event" and event.get("event", {}).get("event_type") == "reasoning_update"
    ]
    assert len(reasoning_updates) == 1
    assert reasoning_updates[0]["message"] == "I am checking existing entries and tags."
    assert not [
        event
        for event in events
        if event.get("type") == "run_event" and event.get("event", {}).get("event_type") == "tool_call_queued"
    ]
    assert events[-1]["event"]["event_type"] == "run_completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert len(detail["runs"]) == 1
    run = detail["runs"][0]
    assert len(run["tool_calls"]) == 0
    assert [event["event_type"] for event in run["events"] if event["event_type"] == "reasoning_update"] == ["reasoning_update"]


def test_stream_message_endpoint_converts_assistant_tool_step_text_into_reasoning_update(client, monkeypatch):
    from backend.services.agent import runtime

    _patch_terminal_success(monkeypatch)
    stream_responses = [
        [
            {
                "type": "text_delta",
                "delta": "I am checking current tags before making any changes.",
            },
            {
                "type": "done",
                "message": {
                    "role": "assistant",
                    "content": "I am checking current tags before making any changes.",
                    "tool_calls": [
                        {
                            "id": "call_terminal",
                            "type": "function",
                            "function": {
                                "name": "terminal",
                                "arguments": json.dumps({"command": "bh tags list"}),
                            },
                        }
                    ],
                },
            },
        ],
        [
            {
                "type": "text_delta",
                "delta": "Done.",
            },
            {
                "type": "done",
                "message": {
                    "role": "assistant",
                    "content": "Done.",
                    "tool_calls": [],
                },
            },
        ],
    ]

    def stream_model(_messages, _db, **_kwargs):
        for event in stream_responses.pop(0):
            yield event

    monkeypatch.setattr(runtime, "call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "process this import")

    reasoning_updates = [
        event["event"]
        for event in events
        if event.get("type") == "run_event" and event.get("event", {}).get("event_type") == "reasoning_update"
    ]
    assert len(reasoning_updates) == 1
    assert reasoning_updates[0]["message"] == "I am checking current tags before making any changes."

    tool_call_events = [
        event
        for event in events
        if event.get("type") == "run_event" and event.get("event", {}).get("event_type", "").startswith("tool_call_")
    ]
    assert [event["event"]["event_type"] for event in tool_call_events] == [
        "tool_call_queued",
        "tool_call_started",
        "tool_call_completed",
    ]
    assert [event["tool_call"]["tool_name"] for event in tool_call_events] == [
        "terminal",
        "terminal",
        "terminal",
    ]
    assert [event["tool_call"]["display_label"] for event in tool_call_events] == [
        "bh tags list",
        "bh tags list",
        "bh tags list",
    ]
    assert [event["tool_call"]["has_full_payload"] for event in tool_call_events] == [False, False, False]
    assert [event["tool_call"]["status"] for event in tool_call_events] == ["queued", "running", "ok"]

    text = "".join(event.get("delta", "") for event in events if event.get("type") == "text_delta")
    assert text == "I am checking current tags before making any changes.Done."

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert len(detail["runs"]) == 1
    run = detail["runs"][0]
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "terminal"
    assert run["tool_calls"][0]["display_label"] == "bh tags list"
    reasoning_run_events = [event for event in run["events"] if event["event_type"] == "reasoning_update"]
    assert len(reasoning_run_events) == 1
    assert reasoning_run_events[0]["message"] == "I am checking current tags before making any changes."
    assert reasoning_run_events[0]["source"] == "assistant_content"


def test_interrupt_running_run_stops_background_processing(client, monkeypatch):
    entered_model = Event()
    release_model = Event()

    def slow_model(_messages):
        entered_model.set()
        release_model.wait(timeout=1.0)
        return {"role": "assistant", "content": "Done."}

    patch_model(monkeypatch, slow_model)
    thread = create_thread(client)

    response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={"content": "please run"},
    )
    response.raise_for_status()
    run = response.json()
    assert run["status"] == "running"
    assert entered_model.wait(timeout=1.0)

    interrupt_response = client.post(f"/api/v1/agent/runs/{run['id']}/interrupt")
    interrupt_response.raise_for_status()
    interrupted = interrupt_response.json()
    assert interrupted["status"] == "failed"
    assert interrupted["error_text"] == "Run interrupted by user."

    release_model.set()
    payload = wait_for_run_completion(client, run["id"], timeout_seconds=2.0)
    assert payload["status"] == "failed"
    assert payload["assistant_message_id"] is None
    assert payload["error_text"] == "Run interrupted by user."


def test_interrupt_completed_run_is_noop(client, monkeypatch):
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Done."})
    thread = create_thread(client)
    run = send_message(client, thread["id"], "complete me")
    assert run["status"] == "completed"

    interrupt_response = client.post(f"/api/v1/agent/runs/{run['id']}/interrupt")
    interrupt_response.raise_for_status()
    interrupted = interrupt_response.json()
    assert interrupted["status"] == "completed"
    assert interrupted["assistant_message_id"] == run["assistant_message_id"]


def test_interrupted_previous_run_context_is_injected_into_followup_turn(client, monkeypatch):
    entered_model = Event()
    release_model = Event()

    def slow_model(_messages):
        entered_model.set()
        release_model.wait(timeout=1.0)
        return {"role": "assistant", "content": "Done."}

    patch_model(monkeypatch, slow_model)
    thread = create_thread(client)

    first_response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/messages",
        data={"content": "Please summarize January spend."},
    )
    first_response.raise_for_status()
    first_run = first_response.json()
    assert first_run["status"] == "running"
    assert entered_model.wait(timeout=1.0)

    interrupt_response = client.post(f"/api/v1/agent/runs/{first_run['id']}/interrupt")
    interrupt_response.raise_for_status()
    interrupted = interrupt_response.json()
    assert interrupted["status"] == "failed"
    assert interrupted["assistant_message_id"] is None
    assert interrupted["error_text"] == "Run interrupted by user."

    release_model.set()
    wait_for_run_completion(client, first_run["id"], timeout_seconds=2.0)

    captured_messages: list[list[dict]] = []

    def followup_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Acknowledged."}

    patch_model(monkeypatch, followup_model)
    followup_run = send_message(client, thread["id"], "continue with Feb and include recurring items")
    assert followup_run["status"] == "completed"
    assert captured_messages

    history = captured_messages[-1]
    followup_user_messages = [message for message in history if message.get("role") == "user"]
    assert followup_user_messages
    followup_user = followup_user_messages[-1]
    followup_content = followup_user.get("content")
    assert isinstance(followup_content, str)
    assert "Previous turn note: the user interrupted your previous response before it completed." in followup_content
    assert 'Interrupted previous user request: "Please summarize January spend."' in followup_content
    assert "Treat that interrupted request as conversation context" in followup_content
    assert "User feedback:" in followup_content
    assert "continue with Feb and include recurring items" in followup_content
    assert followup_content.index("Previous turn note:") < followup_content.index("User feedback:")


def test_run_accumulates_usage_tokens_across_steps(client, monkeypatch):
    _patch_terminal_success(monkeypatch)
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_terminal",
                    "type": "function",
                    "function": {
                        "name": "terminal",
                        "arguments": json.dumps({"command": "bh tags list"}),
                    },
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 3,
                "cache_read_tokens": 2,
                "cache_write_tokens": 1,
            },
        },
        {
            "role": "assistant",
            "content": "I checked tags and found no pending proposals.",
            "usage": {
                "input_tokens": 5,
                "output_tokens": 7,
                "cache_read_tokens": 0,
                "cache_write_tokens": 4,
            },
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "List current tags.")

    assert run["status"] == "completed"
    assert run["input_tokens"] == 15
    assert run["output_tokens"] == 10
    assert run["cache_read_tokens"] == 2
    assert run["cache_write_tokens"] == 5
    assert "input_cost_usd" in run
    assert "output_cost_usd" in run
    assert "total_cost_usd" in run

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    payload = run_detail.json()
    assert payload["input_tokens"] == 15
    assert payload["output_tokens"] == 10
    assert payload["cache_read_tokens"] == 2
    assert payload["cache_write_tokens"] == 5
    assert "input_cost_usd" in payload
    assert "output_cost_usd" in payload
    assert "total_cost_usd" in payload


def test_run_usage_fields_are_null_when_usage_unavailable(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no usage metadata."},
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")

    assert run["status"] == "completed"
    assert run["input_tokens"] is None
    assert run["output_tokens"] is None
    assert run["cache_read_tokens"] is None
    assert run["cache_write_tokens"] is None


def test_run_pricing_handles_missing_cache_usage_fields(client, monkeypatch):
    from backend.config import get_settings
    from backend.services.agent.pricing import UsageCosts

    pricing_calls: list[dict[str, object]] = []

    def fake_calculate_usage_costs(**kwargs):
        pricing_calls.append(kwargs)
        return UsageCosts(input_cost_usd=0.12, output_cost_usd=0.34, total_cost_usd=0.46)

    monkeypatch.setattr("backend.services.agent.serializers.calculate_usage_costs", fake_calculate_usage_costs)
    patch_model(
        monkeypatch,
        lambda _messages: {
            "role": "assistant",
            "content": "Here is the final answer with usage metadata but no cache fields.",
            "usage": {"input_tokens": 10, "output_tokens": 5},
        },
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")

    assert run["status"] == "completed"
    assert run["input_tokens"] == 10
    assert run["output_tokens"] == 5
    assert run["cache_read_tokens"] is None
    assert run["cache_write_tokens"] is None
    assert run["input_cost_usd"] == 0.12
    assert run["output_cost_usd"] == 0.34
    assert run["total_cost_usd"] == 0.46

    run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_response.raise_for_status()
    payload = run_response.json()

    assert payload["cache_read_tokens"] is None
    assert payload["cache_write_tokens"] is None
    assert payload["input_cost_usd"] == 0.12
    assert payload["output_cost_usd"] == 0.34
    assert payload["total_cost_usd"] == 0.46
    assert pricing_calls
    assert all("cache_read_tokens" in call for call in pricing_calls)
    assert all("cache_write_tokens" in call for call in pricing_calls)
    assert any(
        call
        == {
            "model_name": get_settings().agent_model,
            "input_tokens": 10,
            "output_tokens": 5,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
        }
        for call in pricing_calls
    )


def test_run_handles_unknown_tool_calls_as_error(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_unknown",
                    "type": "function",
                    "function": {"name": "unknown_tool", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "assistant",
            "content": "I could not use that tool, but completed the run.",
        },
    ]
    patch_model(monkeypatch, lambda _messages: calls.pop(0))

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Please call a missing tool")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "unknown_tool"
    assert run["tool_calls"][0]["status"] == "error"
    assert run["tool_calls"][0]["output_json"]["summary"] == "unknown tool 'unknown_tool'"


def test_runtime_tool_registry_only_contains_current_tools():
    from backend.services.agent.tool_runtime import TOOLS

    assert set(TOOLS) == {
        "add_user_memory",
        "rename_thread",
        "terminal",
        "send_intermediate_update",
        "read_image",
    }


def test_reviewed_thread_proposals_are_injected_into_followup_turn(client, monkeypatch):
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "Ready."})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create proposal context.")
    assert run["status"] == "completed"

    create_response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers={"X-Bill-Helper-Agent-Run-Id": run["id"]},
        json={
            "change_type": "create_tag",
            "payload_json": {"name": "subscriptions", "type": "expense"},
        },
    )
    create_response.raise_for_status()
    proposal = create_response.json()

    reject_response = client.post(
        f"/api/v1/agent/change-items/{proposal['proposal_id']}/reject",
        json={"note": "Use type recurring instead"},
    )
    reject_response.raise_for_status()

    captured_messages: list[list[dict]] = []

    def second_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Acknowledged review feedback."}

    patch_model(monkeypatch, second_model)
    followup_run = send_message(client, thread["id"], "Try again")
    assert followup_run["status"] == "completed"
    assert captured_messages

    history = captured_messages[-1]
    followup_user = [message for message in history if message.get("role") == "user"][-1]
    followup_content = followup_user.get("content")
    assert isinstance(followup_content, str)
    assert "Review results from your previous proposals:" in followup_content
    assert "bh tags create" in followup_content
    assert "review_action=reject" in followup_content
    assert "Use type recurring instead" in followup_content














































































































def test_requires_provider_credentials_for_send_message(client, monkeypatch):
    from backend.config import get_settings

    settings = get_settings()
    original_model = settings.agent_model
    try:
        settings.agent_model = "openai/gpt-4.1-mini"
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        thread = create_thread(client)
        response = client.post(
            f"/api/v1/agent/threads/{thread['id']}/messages",
            data={"content": "hello"},
        )
        assert response.status_code == 503
        assert "Agent runtime is not configured." in response.text
    finally:
        settings.agent_model = original_model
