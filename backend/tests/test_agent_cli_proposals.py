from __future__ import annotations

from backend.tests.agent_test_utils import create_thread, patch_model, send_message


def _run_headers(run_id: str) -> dict[str, str]:
    return {"X-Bill-Helper-Agent-Run-Id": run_id}


def test_thread_proposal_routes_create_get_and_list(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for proposal context.")

    create_response = client.post(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=_run_headers(run["id"]),
        json={
            "change_type": "create_tag",
            "payload_json": {
                "name": "food",
                "type": "expense",
            },
        },
    )
    create_response.raise_for_status()
    created = create_response.json()
    assert created["proposal_type"] == "tag"
    assert created["change_action"] == "create"
    assert created["payload"]["name"] == "food"

    get_response = client.get(
        f"/api/v1/agent/threads/{thread['id']}/proposals/{created['proposal_short_id']}",
        headers=_run_headers(run["id"]),
    )
    get_response.raise_for_status()
    assert get_response.json()["proposal_id"] == created["proposal_id"]

    list_response = client.get(
        f"/api/v1/agent/threads/{thread['id']}/proposals",
        headers=_run_headers(run["id"]),
        params={"proposal_type": "tag", "limit": 10},
    )
    list_response.raise_for_status()
    listed = list_response.json()
    assert listed["returned_count"] == 1
    assert listed["proposals"][0]["proposal_id"] == created["proposal_id"]


def test_thread_proposal_routes_require_run_header(client, monkeypatch) -> None:
    patch_model(monkeypatch, lambda _messages: {"role": "assistant", "content": "ok"})

    thread = create_thread(client)
    run = send_message(client, thread["id"], "Create a run for proposal context.")
    assert run["status"] == "completed"

    response = client.get(f"/api/v1/agent/threads/{thread['id']}/proposals")

    assert response.status_code == 400
    assert response.json()["detail"] == "Missing X-Bill-Helper-Agent-Run-Id header."
