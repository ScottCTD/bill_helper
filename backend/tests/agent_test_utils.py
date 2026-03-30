from __future__ import annotations

import json
import time
from typing import Any

import pymupdf


def patch_model(monkeypatch, handler: Any) -> None:
    from backend.services.agent import runtime

    def wrapped(messages, _db, **_kwargs):
        return handler(messages)

    monkeypatch.setattr(runtime, "call_model", wrapped)


def create_thread(client) -> dict:
    response = client.post("/api/v1/agent/threads", json={})
    response.raise_for_status()
    return response.json()


def wait_for_run_completion(
    client,
    run_id: str,
    *,
    timeout_seconds: float = 2.0,
) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        run_response = client.get(f"/api/v1/agent/runs/{run_id}")
        run_response.raise_for_status()
        run = run_response.json()
        if run.get("status") != "running":
            return run
        time.sleep(0.01)

    raise AssertionError("Timed out waiting for agent run to complete")


def send_message(
    client,
    thread_id: str,
    content: str,
    *,
    surface: str = "app",
    files: list[tuple[str, bytes, str]] | None = None,
    attachment_ids: list[str] | None = None,
    model_name: str | None = None,
    wait_for_completion: bool = True,
    timeout_seconds: float = 2.0,
) -> dict:
    request_files = [
        ("files", (filename, file_bytes, mime_type))
        for filename, file_bytes, mime_type in files or []
    ]
    request_files.extend(
        ("attachment_ids", (None, attachment_id))
        for attachment_id in attachment_ids or []
    )
    request_data = {
        "content": content,
        "surface": surface,
        "model_name": model_name or "",
    }
    response = client.post(
        f"/api/v1/agent/threads/{thread_id}/messages",
        data=request_data,
        files=request_files or None,
    )
    response.raise_for_status()
    run = response.json()
    if not wait_for_completion or run.get("status") != "running":
        return run

    return wait_for_run_completion(client, run["id"], timeout_seconds=timeout_seconds)


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
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "\n\n".join(part for part in text_parts if part)
    return ""


def collect_sse_events(
    client,
    thread_id: str,
    content: str,
    *,
    surface: str = "app",
    model_name: str | None = None,
) -> list[dict]:
    with client.stream(
        "POST",
        f"/api/v1/agent/threads/{thread_id}/messages/stream",
        data={
            "content": content,
            "surface": surface,
            "model_name": model_name or "",
        },
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
