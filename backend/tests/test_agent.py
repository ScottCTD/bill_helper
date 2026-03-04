from __future__ import annotations

import json
import time
from inspect import signature
from pathlib import Path
from threading import Event

import pymupdf


def create_thread(client) -> dict:
    response = client.post("/api/v1/agent/threads", json={})
    response.raise_for_status()
    return response.json()


def send_message(
    client,
    thread_id: str,
    content: str,
    *,
    files: list[tuple[str, bytes, str]] | None = None,
    wait_for_completion: bool = True,
    timeout_seconds: float = 2.0,
) -> dict:
    request_files = (
        [("files", (filename, file_bytes, mime_type)) for filename, file_bytes, mime_type in files]
        if files
        else None
    )
    response = client.post(
        f"/api/v1/agent/threads/{thread_id}/messages",
        data={"content": content},
        files=request_files,
    )
    response.raise_for_status()
    run = response.json()
    if not wait_for_completion or run.get("status") != "running":
        return run

    run_id = run["id"]
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run_id}")
        run_response.raise_for_status()
        run = run_response.json()
        if run.get("status") != "running":
            return run
        time.sleep(0.01)

    raise AssertionError("Timed out waiting for agent run to complete")


def build_pdf_bytes(page_texts: list[str]) -> bytes:
    document = pymupdf.open()
    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text)
    pdf_bytes = document.tobytes()
    document.close()
    return pdf_bytes


def create_entity(client, name: str, category: str | None = None) -> dict:
    payload = {"name": name}
    if category is not None:
        payload["category"] = category
    response = client.post("/api/v1/entities", json=payload)
    response.raise_for_status()
    return response.json()


def create_tag(
    client,
    name: str,
    *,
    type_name: str | None = None,
    description: str | None = None,
) -> dict:
    payload: dict[str, str] = {"name": name}
    if type_name is not None:
        payload["type"] = type_name
    if description is not None:
        payload["description"] = description
    response = client.post("/api/v1/tags", json=payload)
    response.raise_for_status()
    return response.json()


def flatten_user_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text"]
        return "\n\n".join(part for part in text_parts if part)
    return ""


def patch_model(monkeypatch, handler):
    from backend.services.agent import runtime

    handler_params = signature(handler).parameters
    params = list(handler_params.values())
    accepts_db = len(params) > 1 and params[1].kind in (
        params[1].POSITIONAL_ONLY,
        params[1].POSITIONAL_OR_KEYWORD,
        params[1].VAR_POSITIONAL,
    )
    accepts_kwargs = any(param.kind == param.VAR_KEYWORD for param in handler_params.values())
    accepts_observability = "observability" in handler_params

    def wrapped(messages, db, **kwargs):
        if accepts_db:
            if accepts_kwargs or accepts_observability:
                return handler(messages, db, **kwargs)
            return handler(messages, db)
        if accepts_kwargs or accepts_observability:
            return handler(messages, **kwargs)
        return handler(messages)

    monkeypatch.setattr(runtime, "_call_model", wrapped)


def collect_sse_events(client, thread_id: str, content: str) -> list[dict]:
    with client.stream(
        "POST",
        f"/api/v1/agent/threads/{thread_id}/messages/stream",
        data={"content": content},
    ) as response:
        response.raise_for_status()
        raw = "".join(response.iter_text())

    events: list[dict] = []
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        event_type = ""
        payload = None
        for line in lines:
            if line.startswith("event:"):
                event_type = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                payload = json.loads(line.split(":", 1)[1].strip())
        if isinstance(payload, dict):
            if event_type:
                payload["event_name"] = event_type
            events.append(payload)
    return events


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


def test_thread_detail_includes_configured_model_name(client):
    from backend.config import get_settings

    thread = create_thread(client)
    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert detail["configured_model_name"] == get_settings().agent_model


def test_run_includes_context_tokens(client, monkeypatch):
    monkeypatch.setattr(
        "backend.services.agent.runtime._calculate_context_tokens",
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


def test_thread_detail_computes_current_context_tokens_for_idle_thread(client, monkeypatch):
    monkeypatch.setattr(
        "backend.services.agent.runtime._calculate_context_tokens",
        lambda *, model_name, llm_messages: 123,
    )
    patch_model(
        monkeypatch,
        lambda _messages: {"role": "assistant", "content": "Here is the final answer with no proposals."},
    )

    thread = create_thread(client)
    run = send_message(client, thread["id"], "What happened this month?")
    assert run["context_tokens"] == 123

    monkeypatch.setattr("backend.routers.agent.count_context_tokens", lambda **_kwargs: 777)

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()

    assert detail["current_context_tokens"] == 777
    assert detail["runs"][0]["context_tokens"] == 123


def test_thread_detail_prefers_running_run_context_tokens(client, monkeypatch):
    proceed_second_call = Event()
    entered_second_call = Event()
    call_count = {"value": 0}

    monkeypatch.setattr(
        "backend.services.agent.runtime._calculate_context_tokens",
        lambda *, model_name, llm_messages: len(llm_messages) * 100,
    )
    monkeypatch.setattr("backend.routers.agent.count_context_tokens", lambda **_kwargs: 9999)

    def multi_step_model(_messages):
        call_count["value"] += 1
        if call_count["value"] == 1:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_list_tags",
                        "type": "function",
                        "function": {"name": "list_tags", "arguments": "{}"},
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

    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
        run_response.raise_for_status()
        payload = run_response.json()
        if payload["status"] != "running":
            assert payload["context_tokens"] == 400
            return
        time.sleep(0.01)

    raise AssertionError("Timed out waiting for multi-step run to complete")


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
    deadline = time.monotonic() + 2.0
    final_status = "running"
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
        run_response.raise_for_status()
        final_status = str(run_response.json().get("status") or "running")
        if final_status != "running":
            break
        time.sleep(0.01)
    assert final_status != "running"


def test_delete_thread_removes_uploaded_attachment_files(client, monkeypatch):
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
    assert all(not path.exists() for path in attachment_paths)


def test_default_agent_model_is_openrouter_qwen_qwen3_5_27b():
    from backend.config import get_settings

    assert get_settings().agent_model == "openrouter/qwen/qwen3.5-27b"


def test_model_supports_vision_has_manual_override_for_openrouter_qwen_qwen3_5_27b(monkeypatch):
    from backend.services.agent import message_history

    monkeypatch.setattr(message_history.litellm, "supports_vision", lambda _model: False)

    assert message_history._model_supports_vision("openrouter/qwen/qwen3.5-27b") is True
    assert message_history._model_supports_vision("qwen/qwen3.5-27b") is True


def test_pdf_line_normalization_collapses_internal_whitespace_and_trims_edges():
    from backend.services.agent.message_history import _normalize_pdf_text_lines

    normalized = _normalize_pdf_text_lines("  Invoice   total\tCAD  123.45  \n\n  Line   2  ")
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


def test_pdf_attachment_includes_pymupdf_text_without_pdf_page_images_when_vision_is_disabled(client, monkeypatch):
    from backend.services.agent import message_history

    captured_messages: list[list[dict]] = []

    monkeypatch.setattr(message_history, "_model_supports_vision", lambda _model: False)

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
    assert user_content[0].get("text", "").startswith("PDF file statement.pdf (parsed with PyMuPDF text extraction):")
    assert "Invoice total CAD" in user_content[0].get("text", "")
    assert user_content[1].get("text") == "Please summarize this attachment."

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    first_user = next(message for message in detail["messages"] if message["role"] == "user")
    assert len(first_user["attachments"]) == 1
    assert first_user["attachments"][0]["mime_type"] == "application/pdf"


def test_pdf_attachment_adds_page_images_when_vision_is_enabled(client, monkeypatch):
    from backend.services.agent import message_history

    captured_messages: list[list[dict]] = []

    monkeypatch.setattr(message_history, "_model_supports_vision", lambda _model: True)

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
    assert [part.get("type") for part in user_content] == ["text", "image_url", "image_url", "text"]
    assert user_content[0].get("text", "").startswith("PDF file invoice.pdf (parsed with PyMuPDF text extraction):")
    assert "Page one invoice line item" in user_content[0].get("text", "")
    assert "Page two invoice line item" in user_content[0].get("text", "")
    image_parts = user_content[1:3]
    assert len(image_parts) == 2
    assert all(
        str(part.get("image_url", {}).get("url", "")).startswith("data:image/png;base64,")
        for part in image_parts
    )
    assert user_content[-1].get("text") == "Read every page."


def test_pdf_attachment_uses_tesseract_ocr_when_pymupdf_text_is_empty(client, monkeypatch):
    from backend.services.agent import message_history

    captured_messages: list[list[dict]] = []

    monkeypatch.setattr(message_history, "_model_supports_vision", lambda _model: False)
    monkeypatch.setattr(message_history, "_extract_pdf_text", lambda _file_path: None)
    monkeypatch.setattr(
        message_history,
        "_extract_pdf_text_with_tesseract",
        lambda _file_path: "OCR recovered statement total CAD 123.45",
    )

    def capture_model(messages):
        captured_messages.append(messages)
        return {"role": "assistant", "content": "Processed OCR PDF text."}

    patch_model(monkeypatch, capture_model)

    thread = create_thread(client)
    pdf_bytes = build_pdf_bytes(["Source content is ignored because OCR is mocked."])
    run = send_message(
        client,
        thread["id"],
        "Please summarize this scan.",
        files=[("scan.pdf", pdf_bytes, "application/pdf")],
    )

    assert run["status"] == "completed"
    assert captured_messages

    user_messages = [message for message in captured_messages[-1] if message.get("role") == "user"]
    assert user_messages
    user_content = user_messages[-1].get("content")
    assert isinstance(user_content, list)
    assert [part.get("type") for part in user_content] == ["text", "text"]
    assert user_content[0].get("text", "").startswith("PDF file scan.pdf (parsed with Tesseract OCR; expect imperfect text):")
    assert "OCR recovered statement total CAD 123.45" in user_content[0].get("text", "")
    assert user_content[1].get("text") == "Please summarize this scan."


def test_attachment_parts_stay_before_user_prompt_for_mixed_uploads(client, monkeypatch):
    from backend.services.agent import message_history

    captured_messages: list[list[dict]] = []

    monkeypatch.setattr(message_history, "_model_supports_vision", lambda _model: True)

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
    assert [part.get("type") for part in user_content] == ["text", "image_url", "text", "image_url", "text"]
    assert user_content[0].get("text", "").startswith("PDF file statement.pdf (parsed with PyMuPDF text extraction):")
    assert user_content[2].get("text") == "Image file receipt.png:"
    assert str(user_content[1].get("image_url", {}).get("url", "")).startswith("data:image/png;base64,")
    assert str(user_content[3].get("image_url", {}).get("url", "")).startswith("data:image/png;base64,")
    assert user_content[4].get("text") == "Compare both files."


def test_system_prompt_requires_duplicate_then_reconcile_then_propose_entries():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    duplicate_phrase = "Before proposing any entry, check for duplicates"
    reconcile_phrase = "list existing tags and entities, then propose missing tags/entities first"
    propose_phrase = "Only after duplicate checks and tag/entity reconciliation, propose entries"

    assert duplicate_phrase in prompt
    assert reconcile_phrase in prompt
    assert propose_phrase in prompt
    assert prompt.index(duplicate_phrase) < prompt.index(reconcile_phrase) < prompt.index(propose_phrase)


def test_system_prompt_uses_duplicate_enrichment_before_create():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "If a duplicate exists, check whether the new input adds complementary information." in prompt
    assert "prefer propose_update_entry for the existing entry instead of propose_create_entry." in prompt


def test_system_prompt_requires_canonical_name_normalization_examples():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "Normalize new entity names to canonical, general forms." in prompt
    assert "Normalize new tags to canonical, general descriptors" in prompt
    assert "Starbucks (not SBUX)" in prompt
    assert "Apple (not Apple Store #R121)." in prompt


def test_system_prompt_requires_human_readable_markdown_notes_for_notes_fields():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "For tools that include a markdown_notes field, write human-readable markdown notes" in prompt
    assert "If the content is short, avoid headings." in prompt
    assert "ordered/unordered lists when they improve readability." in prompt


def test_system_prompt_requires_entry_updates_before_tag_delete():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    reference_phrase = "Check whether entries still reference the tag."
    update_phrase = "propose update_entry changes first to remove/replace that tag on affected entries."
    delete_phrase = "Only propose delete_tag after references are cleared."

    assert reference_phrase in prompt
    assert update_phrase in prompt
    assert delete_phrase in prompt
    assert prompt.index(reference_phrase) < prompt.index(update_phrase) < prompt.index(delete_phrase)


def test_system_prompt_guides_pending_proposal_revisions_and_removals():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    revise_phrase = "If the user asks to revise an existing pending proposal, prefer update_pending_proposal"
    remove_phrase = "If the user asks to discard/cancel/remove a pending proposal, use remove_pending_proposal"

    assert revise_phrase in prompt
    assert remove_phrase in prompt
    assert prompt.index(revise_phrase) < prompt.index(remove_phrase)


def test_system_prompt_includes_error_recovery_and_core_identity():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "## Identity" in prompt
    assert "## Rules" in prompt
    assert "append-only policies" not in prompt
    assert "Final message should prioritize a concise direct answer" in prompt
    assert "Include pending review item ids only when pending items exist" not in prompt
    assert "If a tool returns an ERROR" in prompt


def test_system_prompt_requires_first_tool_call_update_for_tool_runs():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "If you need any tool calls for the task, call send_intermediate_update first" in prompt
    assert "before calling other tools." in prompt


def test_system_prompt_requires_sparse_intermediate_updates():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "send_intermediate_update" in prompt
    assert "do not call it on every tool step" in prompt


def test_system_prompt_prefers_parallel_tool_calls_for_independent_work():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "Prefer parallel tool calls when tasks are independent." in prompt
    assert "call them in the same tool-call batch instead of one by one." in prompt


def test_system_prompt_stages_first_proposal_before_parallel_batches():
    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt()
    assert "Do not start a proposal workflow with a large parallel propose_* batch." in prompt
    assert "Start with one representative propose_* call first" in prompt
    assert "After the first proposal succeeds and the pattern is validated" in prompt


def test_system_prompt_includes_current_date_tag():
    from datetime import date

    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt(current_date=date(2026, 2, 10))
    assert "## Current Date (User Timezone: America/Toronto)\n2026-02-10" in prompt


def test_system_prompt_includes_user_memory_when_present():
    from backend.services.agent.prompts import system_prompt

    memory_text = "Prefers terse answers.\nAlways mention CAD explicitly."
    prompt = system_prompt(user_memory=memory_text)

    assert "### User Memory" in prompt
    assert memory_text in prompt
    assert "persistent user-provided background and preferences" in prompt


def test_system_prompt_uses_requested_current_timezone_for_date_label():
    from datetime import date

    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt(current_date=date(2026, 2, 10), current_timezone="America/Vancouver")
    assert "## Current Date (User Timezone: America/Vancouver)\n2026-02-10" in prompt


def test_system_prompt_falls_back_to_toronto_for_invalid_timezone():
    from datetime import date

    from backend.services.agent.prompts import system_prompt

    prompt = system_prompt(current_date=date(2026, 2, 10), current_timezone="Not/AZone")
    assert "## Current Date (User Timezone: America/Toronto)\n2026-02-10" in prompt


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
    assert "## Current Date (User Timezone: America/Toronto)" in system_content
    assert "## Current User Context" in system_content
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
        json={"user_memory": "Prefers terse answers.\nWorks in CAD."},
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
    assert "### User Memory" in system_content
    assert "Prefers terse answers.\nWorks in CAD." in system_content


def test_tool_catalog_removes_legacy_read_tools_and_adds_crud_proposals():
    from backend.services.agent.tools import build_openai_tool_schemas

    names = [tool["function"]["name"] for tool in build_openai_tool_schemas()]
    assert "list_accounts" not in names
    assert "search_entries" not in names
    assert "list_entries" in names
    assert "send_intermediate_update" in names
    assert "propose_update_entry" in names
    assert "propose_delete_entry" in names
    assert "propose_update_tag" in names
    assert "propose_delete_tag" in names
    assert "propose_update_entity" in names
    assert "propose_delete_entity" in names
    assert "update_pending_proposal" in names
    assert "remove_pending_proposal" in names


def test_intermediate_update_tool_description_requires_first_call_for_tool_runs():
    from backend.services.agent.tools import INTERMEDIATE_UPDATE_TOOL_NAME, build_openai_tool_schemas

    tool_by_name = {
        tool["function"]["name"]: tool["function"]
        for tool in build_openai_tool_schemas()
    }
    description = str(tool_by_name[INTERMEDIATE_UPDATE_TOOL_NAME]["description"])
    assert "call this first" in description
    assert "before other tools" in description


def test_list_tags_tool_description_mentions_tag_descriptions():
    from backend.services.agent.tools import build_openai_tool_schemas

    tool_by_name = {
        tool["function"]["name"]: tool["function"]
        for tool in build_openai_tool_schemas()
    }
    description = str(tool_by_name["list_tags"]["description"])
    assert "tag descriptions" in description


def test_entry_proposal_tool_descriptions_define_markdown_notes_style():
    from backend.services.agent.tools import build_openai_tool_schemas

    tool_by_name = {
        tool["function"]["name"]: tool["function"]
        for tool in build_openai_tool_schemas()
    }
    create_description = str(tool_by_name["propose_create_entry"]["description"])
    update_description = str(tool_by_name["propose_update_entry"]["description"])

    assert "pending create_entity proposals already in the current thread" in create_description
    assert "When markdown_notes is provided" in create_description
    assert "avoid headings" in create_description
    assert "ordered/unordered lists" in create_description

    assert "When patch.markdown_notes is provided" in update_description
    assert "avoid headings" in update_description
    assert "ordered/unordered lists" in update_description


def test_run_persists_tool_calls(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_list_tags",
                    "type": "function",
                    "function": {"name": "list_tags", "arguments": "{}"},
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
    assert run["tool_calls"][0]["tool_name"] == "list_tags"
    assert run["tool_calls"][0]["status"] == "ok"
    assert isinstance(run["tool_calls"][0]["output_text"], str)
    assert run["tool_calls"][0]["output_text"].startswith("OK")

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    payload = run_detail.json()
    assert payload["assistant_message_id"] == run["assistant_message_id"]
    assert len(payload["tool_calls"]) == 1


def test_list_tags_tool_output_includes_tag_descriptions(client, monkeypatch):
    create_tag(
        client,
        "groceries",
        type_name="expense",
        description="Food and household staples from grocery stores and supermarkets.",
    )

    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_list_tags",
                    "type": "function",
                    "function": {"name": "list_tags", "arguments": "{}"},
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

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 1
    output_json = run["tool_calls"][0]["output_json"]
    assert output_json["status"] == "OK"
    assert output_json["tags"][0]["name"] == "groceries"
    assert output_json["tags"][0]["type"] == "expense"
    assert output_json["tags"][0]["description"] == "Food and household staples from grocery stores and supermarkets."
    assert "description: Food and household staples from grocery stores and supermarkets." in run["tool_calls"][0]["output_text"]


def test_run_persists_assistant_tool_step_text_as_intermediate_update(client, monkeypatch):
    calls = [
        {
            "role": "assistant",
            "content": "I am checking current tags before making any changes.",
            "tool_calls": [
                {
                    "id": "call_list_tags",
                    "type": "function",
                    "function": {"name": "list_tags", "arguments": "{}"},
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
    assert len(run["tool_calls"]) == 2
    assert run["tool_calls"][0]["tool_name"] == "send_intermediate_update"
    assert run["tool_calls"][0]["output_json"]["message"] == "I am checking current tags before making any changes."
    assert run["tool_calls"][0]["output_json"]["source"] == "assistant_content"
    assert run["tool_calls"][1]["tool_name"] == "list_tags"


def test_final_message_strips_empty_pending_review_footer(client, monkeypatch):
    patch_model(
        monkeypatch,
        lambda _messages: {
            "role": "assistant",
            "content": (
                "Here is your dashboard summary.\n\n"
                "Tools used (high level): get_dashboard_summary (dashboard snapshot for 2026-02) "
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
    def slow_model(_messages):
        time.sleep(0.35)
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

    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
        run_response.raise_for_status()
        payload = run_response.json()
        if payload["status"] != "running":
            assert payload["status"] == "completed"
            assert payload["assistant_message_id"] is not None
            return
        time.sleep(0.02)

    raise AssertionError("Run did not complete in time")


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

    monkeypatch.setattr(runtime, "_call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "say hello")

    assert events
    assert events[0]["type"] == "run_started"
    text = "".join(event.get("delta", "") for event in events if event.get("type") == "text_delta")
    assert text == "Hello"
    assert events[-1]["type"] == "run_completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assistant_messages = [message for message in detail["messages"] if message["role"] == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0]["content_markdown"] == "Hello"


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

    monkeypatch.setattr(runtime, "_call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "process this import")

    reasoning_updates = [event for event in events if event.get("type") == "reasoning_update"]
    assert len(reasoning_updates) == 1
    assert reasoning_updates[0]["message"] == "I am checking existing entries and tags."
    assert not [event for event in events if event.get("type") == "tool_call"]
    assert events[-1]["type"] == "run_completed"

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert len(detail["runs"]) == 1
    run = detail["runs"][0]
    assert len(run["tool_calls"]) == 1
    assert run["tool_calls"][0]["tool_name"] == "send_intermediate_update"
    assert run["tool_calls"][0]["output_json"]["message"] == "I am checking existing entries and tags."


def test_stream_message_endpoint_converts_assistant_tool_step_text_into_reasoning_update(client, monkeypatch):
    from backend.services.agent import runtime

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
                            "id": "call_list_tags",
                            "type": "function",
                            "function": {
                                "name": "list_tags",
                                "arguments": "{}",
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

    monkeypatch.setattr(runtime, "_call_model_stream", stream_model)

    thread = create_thread(client)
    events = collect_sse_events(client, thread["id"], "process this import")

    reasoning_updates = [event for event in events if event.get("type") == "reasoning_update"]
    assert len(reasoning_updates) == 1
    assert reasoning_updates[0]["message"] == "I am checking current tags before making any changes."

    tool_calls = [event for event in events if event.get("type") == "tool_call"]
    assert len(tool_calls) == 1
    assert tool_calls[0]["tool_name"] == "list_tags"

    text = "".join(event.get("delta", "") for event in events if event.get("type") == "text_delta")
    assert text == "I am checking current tags before making any changes.Done."

    detail_response = client.get(f"/api/v1/agent/threads/{thread['id']}")
    detail_response.raise_for_status()
    detail = detail_response.json()
    assert len(detail["runs"]) == 1
    run = detail["runs"][0]
    assert len(run["tool_calls"]) == 2
    assert run["tool_calls"][0]["tool_name"] == "send_intermediate_update"
    assert run["tool_calls"][0]["output_json"]["message"] == "I am checking current tags before making any changes."
    assert run["tool_calls"][0]["output_json"]["source"] == "assistant_content"
    assert run["tool_calls"][1]["tool_name"] == "list_tags"


def test_model_observability_uses_thread_as_session_id(client, monkeypatch):
    captured_observability: list[dict] = []

    def capture_model(_messages, _db, *, observability=None):
        if isinstance(observability, dict):
            captured_observability.append(observability)
        return {"role": "assistant", "content": "Done."}

    patch_model(monkeypatch, capture_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "hello")

    assert run["status"] == "completed"
    assert captured_observability
    context = captured_observability[0]
    assert context["session_id"] == thread["id"]
    assert context["trace"]["trace_id"] == thread["id"]
    assert context["trace"]["run_id"] == run["id"]


def test_interrupt_running_run_stops_background_processing(client, monkeypatch):
    def slow_model(_messages):
        time.sleep(0.35)
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

    interrupt_response = client.post(f"/api/v1/agent/runs/{run['id']}/interrupt")
    interrupt_response.raise_for_status()
    interrupted = interrupt_response.json()
    assert interrupted["status"] == "failed"
    assert interrupted["error_text"] == "Run interrupted by user."

    time.sleep(0.45)
    run_response = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_response.raise_for_status()
    payload = run_response.json()
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
    def slow_model(_messages):
        time.sleep(0.35)
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

    interrupt_response = client.post(f"/api/v1/agent/runs/{first_run['id']}/interrupt")
    interrupt_response.raise_for_status()
    interrupted = interrupt_response.json()
    assert interrupted["status"] == "failed"
    assert interrupted["assistant_message_id"] is None
    assert interrupted["error_text"] == "Run interrupted by user."

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
    calls = [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_list_tags",
                    "type": "function",
                    "function": {"name": "list_tags", "arguments": "{}"},
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


def test_proposal_creation_for_each_create_change_type(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done. Please review pending items."}
        user_message = next(message for message in reversed(messages) if message["role"] == "user")
        content = flatten_user_content(user_message["content"])
        if "tag" in content:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_tag",
                        "type": "function",
                        "function": {
                            "name": "propose_create_tag",
                            "arguments": json.dumps(
                                {
                                    "name": "groceries",
                                    "type": "daily",
                                }
                            ),
                        },
                    }
                ],
            }
        if "entity" in content:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_entity",
                        "type": "function",
                        "function": {
                            "name": "propose_create_entity",
                            "arguments": json.dumps(
                                {
                                    "name": "Costco",
                                    "category": "merchant",
                                }
                            ),
                        },
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-01-03",
                                "name": "Coffee",
                                "amount_minor": 550,
                                "currency_code": "USD",
                                "from_entity": "Main Checking",
                                "to_entity": "Coffee Shop",
                                "tags": ["food"],
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread_tag = create_thread(client)
    thread_entity = create_thread(client)
    thread_entry = create_thread(client)
    create_tag(client, "food")
    create_entity(client, "Main Checking", category="account")
    create_entity(client, "Coffee Shop", category="merchant")
    run_tag = send_message(client, thread_tag["id"], "Please propose a new tag.")
    run_entity = send_message(client, thread_entity["id"], "Please propose a new entity.")
    run_entry = send_message(client, thread_entry["id"], "Please propose a new entry.")

    assert run_tag["change_items"][0]["change_type"] == "create_tag"
    assert run_entity["change_items"][0]["change_type"] == "create_entity"
    assert run_entry["change_items"][0]["change_type"] == "create_entry"
    assert run_tag["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_entity["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_entry["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run_tag["tool_calls"][0]["output_json"]["proposal_id"] == run_tag["change_items"][0]["id"]
    assert run_entity["tool_calls"][0]["output_json"]["proposal_id"] == run_entity["change_items"][0]["id"]
    assert run_entry["tool_calls"][0]["output_json"]["proposal_id"] == run_entry["change_items"][0]["id"]
    assert "account_id" not in run_entry["change_items"][0]["payload_json"]


def test_entry_proposal_can_reference_pending_entity_in_same_turn(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done. Please review pending items."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps(
                            {
                                "name": "Molly Tea",
                                "category": "merchant",
                            }
                        ),
                    },
                },
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-01-04",
                                "name": "Bubble tea",
                                "amount_minor": 850,
                                "currency_code": "CAD",
                                "from_entity": "Main Checking",
                                "to_entity": "Molly Tea",
                            }
                        ),
                    },
                },
            ],
        }

    patch_model(monkeypatch, fake_model)
    create_entity(client, "Main Checking", category="account")
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Log my bubble tea purchase from Molly Tea")

    assert run["status"] == "completed"
    assert len(run["tool_calls"]) == 2
    assert len(run["change_items"]) == 2

    change_items_by_type = {item["change_type"]: item for item in run["change_items"]}
    assert change_items_by_type["create_entity"]["payload_json"]["name"] == "Molly Tea"
    assert change_items_by_type["create_entry"]["payload_json"]["to_entity"] == "Molly Tea"
    assert all(tool_call["output_json"]["status"] == "OK" for tool_call in run["tool_calls"])


def test_entry_approval_waits_for_pending_entity_dependency(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done. Please review pending items."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps(
                            {
                                "name": "Molly Tea",
                                "category": "merchant",
                            }
                        ),
                    },
                },
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-01-04",
                                "name": "Bubble tea",
                                "amount_minor": 850,
                                "currency_code": "CAD",
                                "from_entity": "Main Checking",
                                "to_entity": "Molly Tea",
                            }
                        ),
                    },
                },
            ],
        }

    patch_model(monkeypatch, fake_model)
    create_entity(client, "Main Checking", category="account")
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Log my bubble tea purchase from Molly Tea")

    entity_item = next(item for item in run["change_items"] if item["change_type"] == "create_entity")
    entry_item = next(item for item in run["change_items"] if item["change_type"] == "create_entry")

    approve_entry_first = client.post(f"/api/v1/agent/change-items/{entry_item['id']}/approve", json={})
    assert approve_entry_first.status_code == 422
    assert "Approve or reject those entity proposals first." in approve_entry_first.text

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    pending_entry = next(
        item for item in run_detail.json()["change_items"] if item["id"] == entry_item["id"]
    )
    assert pending_entry["status"] == "PENDING_REVIEW"
    assert pending_entry["review_actions"] == []

    approve_entity = client.post(f"/api/v1/agent/change-items/{entity_item['id']}/approve", json={})
    approve_entity.raise_for_status()
    assert approve_entity.json()["status"] == "APPLIED"

    approve_entry_second = client.post(f"/api/v1/agent/change-items/{entry_item['id']}/approve", json={})
    approve_entry_second.raise_for_status()
    assert approve_entry_second.json()["status"] == "APPLIED"


def test_rejecting_pending_entity_keeps_dependent_entry_pending_until_revised(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done. Please review pending items."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps(
                            {
                                "name": "Molly Tea",
                                "category": "merchant",
                            }
                        ),
                    },
                },
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-01-04",
                                "name": "Bubble tea",
                                "amount_minor": 850,
                                "currency_code": "CAD",
                                "from_entity": "Main Checking",
                                "to_entity": "Molly Tea",
                            }
                        ),
                    },
                },
            ],
        }

    patch_model(monkeypatch, fake_model)
    create_entity(client, "Main Checking", category="account")
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Log my bubble tea purchase from Molly Tea")

    entity_item = next(item for item in run["change_items"] if item["change_type"] == "create_entity")
    entry_item = next(item for item in run["change_items"] if item["change_type"] == "create_entry")

    reject_response = client.post(
        f"/api/v1/agent/change-items/{entity_item['id']}/reject",
        json={"note": "Wrong merchant"},
    )
    reject_response.raise_for_status()
    assert reject_response.json()["status"] == "REJECTED"

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    refreshed_items = {item["id"]: item for item in run_detail.json()["change_items"]}
    pending_entry = refreshed_items[entry_item["id"]]

    assert pending_entry["status"] == "PENDING_REVIEW"
    assert pending_entry["review_note"] is None
    assert pending_entry["review_actions"] == []

    approve_entry = client.post(f"/api/v1/agent/change-items/{entry_item['id']}/approve", json={})
    assert approve_entry.status_code == 422
    assert "Entry references missing entity 'Molly Tea'." in approve_entry.text


def test_duplicate_pending_entity_creation_is_rejected_in_same_thread(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps(
                            {
                                "name": "Molly Tea",
                                "category": "merchant",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)

    first_run = send_message(client, thread["id"], "Create Molly Tea")
    assert first_run["change_items"][0]["status"] == "PENDING_REVIEW"

    second_run = send_message(client, thread["id"], "Create Molly Tea again")
    assert second_run["change_items"] == []
    assert second_run["tool_calls"][0]["output_json"]["status"] == "ERROR"
    assert second_run["tool_calls"][0]["output_json"]["summary"] == (
        "entity already has a pending creation proposal in this thread"
    )


def test_approve_and_reapprove_conflict(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Tag proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_tag",
                    "type": "function",
                    "function": {
                        "name": "propose_create_tag",
                        "arguments": json.dumps(
                            {
                                "name": "subscriptions",
                                "type": "recurring",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose tag subscriptions")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
    approve_response.raise_for_status()
    approved = approve_response.json()
    assert approved["status"] == "APPLIED"
    assert approved["applied_resource_type"] == "tag"
    tags = client.get("/api/v1/tags").json()
    assert any(tag["name"] == "subscriptions" for tag in tags)

    second_approve = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
    assert second_approve.status_code == 409


def test_reject_flow(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entity proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps(
                            {
                                "name": "Temp Vendor",
                                "category": "merchant",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose entity Temp Vendor")
    item_id = run["change_items"][0]["id"]

    reject_response = client.post(f"/api/v1/agent/change-items/{item_id}/reject", json={"note": "Wrong merchant"})
    reject_response.raise_for_status()
    rejected = reject_response.json()
    assert rejected["status"] == "REJECTED"

    entities = client.get("/api/v1/entities").json()
    assert all(entity["name"] != "Temp Vendor" for entity in entities)


def test_propose_delete_tag_is_blocked_when_tag_is_referenced(client, monkeypatch):
    create_entry_response = client.post(
        "/api/v1/entries",
        json={
            "kind": "EXPENSE",
            "occurred_at": "2026-01-09",
            "name": "Tagged expense",
            "amount_minor": 990,
            "currency_code": "USD",
            "from_entity": "Main Checking",
            "to_entity": "Grocery Store",
            "tags": ["groceries"],
        },
    )
    create_entry_response.raise_for_status()

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Cannot delete that tag while it is in use."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_delete_tag",
                    "type": "function",
                    "function": {
                        "name": "propose_delete_tag",
                        "arguments": json.dumps({"name": "groceries"}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Delete the groceries tag")

    assert run["status"] == "completed"
    assert run["change_items"] == []
    assert len(run["tool_calls"]) == 1
    tool_output = run["tool_calls"][0]["output_json"]
    assert tool_output["status"] == "ERROR"
    assert "cannot delete tag while it is referenced" in tool_output["summary"]
    details = tool_output["details"]
    assert details["name"] == "groceries"
    assert details["referenced_entry_count"] == 1


def test_delete_tag_apply_fails_if_tag_becomes_referenced_before_approval(client, monkeypatch):
    create_tag_response = client.post("/api/v1/tags", json={"name": "stale-tag", "type": "misc"})
    create_tag_response.raise_for_status()

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Tag delete proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_delete_tag",
                    "type": "function",
                    "function": {
                        "name": "propose_delete_tag",
                        "arguments": json.dumps({"name": "stale-tag"}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Delete stale-tag")
    item_id = run["change_items"][0]["id"]

    create_entry_response = client.post(
        "/api/v1/entries",
        json={
            "kind": "EXPENSE",
            "occurred_at": "2026-01-12",
            "name": "Late tag link",
            "amount_minor": 1450,
            "currency_code": "USD",
            "from_entity": "Main Checking",
            "to_entity": "Cafe",
            "tags": ["stale-tag"],
        },
    )
    create_entry_response.raise_for_status()

    approve_response = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
    assert approve_response.status_code == 422
    assert "cannot be deleted because it is referenced" in approve_response.text

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    refreshed_item = next(item for item in run_detail.json()["change_items"] if item["id"] == item_id)
    assert refreshed_item["status"] == "APPLY_FAILED"
    assert "cannot be deleted because it is referenced" in (refreshed_item["review_note"] or "")


def test_entry_approve_applies_entry_and_allows_override(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entry proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-01-09",
                                "name": "Lunch draft",
                                "amount_minor": 1800,
                                "currency_code": "USD",
                                "from_entity": "Main Checking",
                                "to_entity": "Lunch Spot",
                                "tags": ["food"],
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    create_tag(client, "food")
    create_tag(client, "team")
    create_entity(client, "Main Checking", category="account")
    create_entity(client, "Lunch Spot", category="merchant")
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose an entry for lunch")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/approve",
        json={
            "payload_override": {
                "kind": "EXPENSE",
                "date": "2026-01-09",
                "name": "Lunch confirmed by reviewer",
                "amount_minor": 1800,
                "currency_code": "USD",
                "from_entity": "Main Checking",
                "to_entity": "Lunch Spot",
                "tags": ["food", "team"],
            }
        },
    )
    approve_response.raise_for_status()
    approved = approve_response.json()
    assert approved["status"] == "APPLIED"
    assert approved["applied_resource_type"] == "entry"

    entries = client.get("/api/v1/entries", params={"source": "Lunch confirmed by reviewer"})
    entries.raise_for_status()
    payload = entries.json()
    assert payload["total"] == 1
    assert payload["items"][0]["name"] == "Lunch confirmed by reviewer"
    assert "status" not in payload["items"][0]


def test_entry_approve_apply_failure_marks_item_failed(client, monkeypatch):
    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entry proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entry",
                        "arguments": json.dumps(
                            {
                                "kind": "EXPENSE",
                                "date": "2026-01-10",
                                "name": "Draft entry",
                                "amount_minor": 1200,
                                "currency_code": "USD",
                                "from_entity": "Main Checking",
                                "to_entity": "Store",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    create_entity(client, "Main Checking", category="account")
    create_entity(client, "Store", category="merchant")
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Propose entry")
    item_id = run["change_items"][0]["id"]

    approve_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/approve",
        json={
            "note": "attempt apply",
            "payload_override": {
                "kind": "EXPENSE",
                "date": "2026-01-10",
                "name": "Missing from_entity",
                "amount_minor": 1200,
                "currency_code": "USD",
                "to_entity": "Store",
            },
        },
    )
    assert approve_response.status_code == 422
    assert "from_entity" in approve_response.text

    run_detail = client.get(f"/api/v1/agent/runs/{run['id']}")
    run_detail.raise_for_status()
    refreshed_item = next(item for item in run_detail.json()["change_items"] if item["id"] == item_id)
    assert refreshed_item["status"] == "APPLY_FAILED"
    assert "apply failed" in (refreshed_item["review_note"] or "")
    assert any(action["action"] == "approve" for action in refreshed_item["review_actions"])


def test_update_entry_selector_ambiguity_is_reported_to_agent(client, monkeypatch):
    # Prepare duplicate selector candidates.
    for _ in range(2):
        create_response = client.post(
            "/api/v1/entries",
            json={
                "kind": "EXPENSE",
                "occurred_at": "2026-01-11",
                "name": "Ambiguous Lunch",
                "amount_minor": 2500,
                "currency_code": "USD",
                "from_entity": "Main Checking",
                "to_entity": "Lunch Spot",
                "tags": ["food"],
            },
        )
        create_response.raise_for_status()

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Selector is ambiguous; please clarify which entry to update."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_update_entry",
                    "type": "function",
                    "function": {
                        "name": "propose_update_entry",
                        "arguments": json.dumps(
                            {
                                "selector": {
                                    "date": "2026-01-11",
                                    "amount_minor": 2500,
                                    "from_entity": "Main Checking",
                                    "to_entity": "Lunch Spot",
                                    "name": "Ambiguous Lunch",
                                },
                                "patch": {
                                    "name": "Ambiguous Lunch (updated)",
                                },
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Update that lunch entry")

    assert run["status"] == "completed"
    assert run["change_items"] == []
    assert len(run["tool_calls"]) == 1
    tool_output = run["tool_calls"][0]["output_json"]
    assert tool_output["status"] == "ERROR"
    assert "ambiguous selector" in tool_output["summary"]


def test_update_entry_accepts_stringified_selector_and_patch(client, monkeypatch):
    create_response = client.post(
        "/api/v1/entries",
        json={
            "kind": "EXPENSE",
            "occurred_at": "2025-12-26",
            "name": "Uniqlo Canada",
            "amount_minor": 5900,
            "currency_code": "CAD",
            "from_entity": "Main Checking",
            "to_entity": "Uniqlo Canada",
            "tags": ["shopping"],
        },
    )
    create_response.raise_for_status()

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Update proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_update_entry_stringified",
                    "type": "function",
                    "function": {
                        "name": "propose_update_entry",
                        "arguments": json.dumps(
                            {
                                "selector": json.dumps(
                                    {
                                        "date": "2025-12-26",
                                        "amount_minor": 5900,
                                        "from_entity": "Main Checking",
                                        "to_entity": "Uniqlo Canada",
                                        "name": "Uniqlo Canada",
                                    }
                                ),
                                "patch": json.dumps(
                                    {
                                        "name": "Uniqlo",
                                    }
                                ),
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    run = send_message(client, thread["id"], "Normalize the Uniqlo entry name")

    assert run["status"] == "completed"
    assert len(run["change_items"]) == 1
    assert run["change_items"][0]["change_type"] == "update_entry"
    assert run["change_items"][0]["status"] == "PENDING_REVIEW"
    assert run["change_items"][0]["payload_json"]["selector"]["name"] == "Uniqlo Canada"
    assert run["change_items"][0]["payload_json"]["patch"]["name"] == "Uniqlo"
    assert run["tool_calls"][0]["output_json"]["status"] == "OK"


def test_reviewed_items_are_injected_into_followup_turn(client, monkeypatch):
    def first_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Tag proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_tag",
                    "type": "function",
                    "function": {
                        "name": "propose_create_tag",
                        "arguments": json.dumps(
                            {
                                "name": "tmp-tag",
                                "type": "tmp",
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, first_model)
    thread = create_thread(client)
    first_run = send_message(client, thread["id"], "Create a temporary tag")
    item_id = first_run["change_items"][0]["id"]

    reject_response = client.post(
        f"/api/v1/agent/change-items/{item_id}/reject",
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
    followup_user_messages = [message for message in history if message.get("role") == "user"]
    assert followup_user_messages
    followup_user = followup_user_messages[-1]
    followup_content = followup_user.get("content")
    assert isinstance(followup_content, str)
    assert "Review results from your previous proposals:" in followup_content
    assert "propose_create_tag" in followup_content
    assert "review_action=reject" in followup_content
    assert "Use type recurring instead" in followup_content
    assert followup_content.index("Review results from your previous proposals:") < followup_content.index("User feedback:")
    assert followup_content.index("User feedback:") < followup_content.index("Try again")


def test_propose_tools_allowed_when_pending_reviews_exist(client, monkeypatch):
    # First run creates a pending proposal and we intentionally skip review.
    def first_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Tag proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_tag",
                    "type": "function",
                    "function": {
                        "name": "propose_create_tag",
                        "arguments": json.dumps({"name": "pending-tag", "type": "misc"}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, first_model)
    thread = create_thread(client)
    first_run = send_message(client, thread["id"], "Create tag pending-tag")
    assert first_run["change_items"][0]["status"] == "PENDING_REVIEW"

    # Second run creates another proposal while first one is still pending.
    def second_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Entity proposal created."}
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_propose_entity",
                    "type": "function",
                    "function": {
                        "name": "propose_create_entity",
                        "arguments": json.dumps({"name": "Blocked Entity", "category": "merchant"}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, second_model)
    second_run = send_message(client, thread["id"], "Create blocked entity")
    assert second_run["status"] == "completed"
    assert len(second_run["change_items"]) == 1
    assert second_run["change_items"][0]["status"] == "PENDING_REVIEW"
    assert second_run["change_items"][0]["change_type"] == "create_entity"
    assert second_run["tool_calls"][0]["output_json"]["status"] == "OK"
    assert second_run["tool_calls"][0]["output_json"]["proposal_id"] == second_run["change_items"][0]["id"]


def test_update_pending_proposal_tool_updates_existing_item(client, monkeypatch):
    pending_short_id: str | None = None
    pending_item_id: str | None = None

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done."}
        user_message = next(message for message in reversed(messages) if message["role"] == "user")
        content = flatten_user_content(user_message["content"])
        if "create initial proposal" in content:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_entry",
                        "type": "function",
                        "function": {
                            "name": "propose_create_entry",
                            "arguments": json.dumps(
                                {
                                    "kind": "EXPENSE",
                                    "date": "2026-01-14",
                                    "name": "Lunch",
                                    "amount_minor": 1200,
                                    "currency_code": "CAD",
                                    "from_entity": "Main Checking",
                                    "to_entity": "Lunch Spot",
                                    "tags": ["food"],
                                }
                            ),
                        },
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_update_pending",
                    "type": "function",
                    "function": {
                        "name": "update_pending_proposal",
                        "arguments": json.dumps(
                            {
                                "proposal_id": pending_short_id,
                                "patch_map": {
                                    "date": "2026-01-15",
                                    "amount_minor": 1350,
                                },
                            }
                        ),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    create_tag(client, "food")
    create_entity(client, "Main Checking", category="account")
    create_entity(client, "Lunch Spot", category="merchant")
    thread = create_thread(client)
    first_run = send_message(client, thread["id"], "Please create initial proposal")
    pending_item_id = first_run["change_items"][0]["id"]
    pending_short_id = pending_item_id[:8]

    second_run = send_message(client, thread["id"], "Please revise that pending proposal")
    assert second_run["status"] == "completed"
    assert second_run["change_items"] == []
    assert len(second_run["tool_calls"]) == 1
    update_output = second_run["tool_calls"][0]["output_json"]
    assert update_output["status"] == "OK"
    assert update_output["proposal_id"] == pending_item_id
    assert "amount_minor" in update_output["patch_fields"]
    assert "date" in update_output["patch_fields"]

    run_detail = client.get(f"/api/v1/agent/runs/{first_run['id']}")
    run_detail.raise_for_status()
    updated_item = run_detail.json()["change_items"][0]
    assert updated_item["id"] == pending_item_id
    assert updated_item["status"] == "PENDING_REVIEW"
    assert updated_item["payload_json"]["date"] == "2026-01-15"
    assert updated_item["payload_json"]["amount_minor"] == 1350


def test_remove_pending_proposal_tool_removes_existing_item(client, monkeypatch):
    pending_short_id: str | None = None
    pending_item_id: str | None = None

    def fake_model(messages):
        if messages[-1]["role"] == "tool":
            return {"role": "assistant", "content": "Done."}
        user_message = next(message for message in reversed(messages) if message["role"] == "user")
        content = flatten_user_content(user_message["content"])
        if "create initial proposal" in content:
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_tag",
                        "type": "function",
                        "function": {
                            "name": "propose_create_tag",
                            "arguments": json.dumps({"name": "Temporary Tag", "type": "expense"}),
                        },
                    }
                ],
            }
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_remove_pending",
                    "type": "function",
                    "function": {
                        "name": "remove_pending_proposal",
                        "arguments": json.dumps({"proposal_id": pending_short_id}),
                    },
                }
            ],
        }

    patch_model(monkeypatch, fake_model)
    thread = create_thread(client)
    first_run = send_message(client, thread["id"], "Please create initial proposal")
    pending_item_id = first_run["change_items"][0]["id"]
    pending_short_id = pending_item_id[:8]

    second_run = send_message(client, thread["id"], "Please remove that pending proposal")
    assert second_run["status"] == "completed"
    assert second_run["change_items"] == []
    assert len(second_run["tool_calls"]) == 1

    remove_output = second_run["tool_calls"][0]["output_json"]
    assert remove_output["status"] == "OK"
    assert remove_output["proposal_id"] == pending_item_id
    assert remove_output["proposal_short_id"] == pending_short_id
    assert remove_output["removed"] is True

    run_detail = client.get(f"/api/v1/agent/runs/{first_run['id']}")
    run_detail.raise_for_status()
    assert run_detail.json()["change_items"] == []


def test_create_entry_uses_default_currency_when_omitted(client, monkeypatch):
    from backend.config import get_settings

    settings = get_settings()
    original_currency = settings.default_currency_code

    try:
        settings.default_currency_code = "CAD"

        def fake_model(messages):
            if messages[-1]["role"] == "tool":
                return {"role": "assistant", "content": "Entry proposal created."}
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_propose_entry",
                        "type": "function",
                        "function": {
                            "name": "propose_create_entry",
                            "arguments": json.dumps(
                                {
                                    "kind": "EXPENSE",
                                    "date": "2026-01-13",
                                    "name": "Transit",
                                    "amount_minor": 450,
                                    "from_entity": "Main Checking",
                                    "to_entity": "Transit Agency",
                                    "tags": ["transport"],
                                }
                            ),
                        },
                    }
                ],
            }

        patch_model(monkeypatch, fake_model)
        create_tag(client, "transport")
        create_entity(client, "Main Checking", category="account")
        create_entity(client, "Transit Agency", category="merchant")
        thread = create_thread(client)
        run = send_message(client, thread["id"], "Propose transit entry")
        item_id = run["change_items"][0]["id"]

        approve_response = client.post(f"/api/v1/agent/change-items/{item_id}/approve", json={})
        approve_response.raise_for_status()

        entries = client.get("/api/v1/entries", params={"source": "Transit"})
        entries.raise_for_status()
        payload = entries.json()
        assert payload["total"] == 1
        assert payload["items"][0]["currency_code"] == "CAD"
    finally:
        settings.default_currency_code = original_currency


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
