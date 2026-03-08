from __future__ import annotations

import json

from backend.schemas_finance import RuntimeSettingsUpdate
from telegram._http import HttpResponse
from telegram.bill_helper_api import AttachmentUpload, BillHelperApiClient


def test_thread_endpoints_and_settings_use_existing_backend_routes():
    requests = []
    responses = iter(
        [
            HttpResponse(
                status_code=200,
                headers={},
                body=json.dumps(
                    [
                        {
                            "id": "thread-1",
                            "title": "Receipts",
                            "created_at": "2026-03-08T00:00:00Z",
                            "updated_at": "2026-03-08T00:00:00Z",
                            "last_message_preview": "Latest",
                            "pending_change_count": 0,
                            "has_running_run": False,
                        }
                    ]
                ).encode("utf-8"),
            ),
            HttpResponse(
                status_code=201,
                headers={},
                body=json.dumps(
                    {
                        "id": "thread-2",
                        "title": "New thread",
                        "created_at": "2026-03-08T00:00:00Z",
                        "updated_at": "2026-03-08T00:00:00Z",
                    }
                ).encode("utf-8"),
            ),
            HttpResponse(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "thread": {
                            "id": "thread-1",
                            "title": "Receipts",
                            "created_at": "2026-03-08T00:00:00Z",
                            "updated_at": "2026-03-08T00:00:00Z",
                        },
                        "messages": [],
                        "runs": [],
                        "configured_model_name": "openrouter/qwen/qwen3.5-27b",
                        "current_context_tokens": 64,
                    }
                ).encode("utf-8"),
            ),
            HttpResponse(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "current_user_name": "admin",
                        "user_memory": None,
                        "default_currency_code": "CAD",
                        "dashboard_currency_code": "CAD",
                        "agent_model": "openrouter/qwen/qwen3.5-27b",
                        "agent_max_steps": 100,
                        "agent_bulk_max_concurrent_threads": 4,
                        "agent_retry_max_attempts": 3,
                        "agent_retry_initial_wait_seconds": 0.25,
                        "agent_retry_max_wait_seconds": 4.0,
                        "agent_retry_backoff_multiplier": 2.0,
                        "agent_max_image_size_bytes": 5242880,
                        "agent_max_images_per_message": 4,
                        "agent_base_url": None,
                        "agent_api_key_configured": False,
                        "overrides": {"agent_api_key_configured": False},
                    }
                ).encode("utf-8"),
            ),
            HttpResponse(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "current_user_name": "admin",
                        "user_memory": None,
                        "default_currency_code": "CAD",
                        "dashboard_currency_code": "CAD",
                        "agent_model": "openai/gpt-4.1",
                        "agent_max_steps": 100,
                        "agent_bulk_max_concurrent_threads": 4,
                        "agent_retry_max_attempts": 3,
                        "agent_retry_initial_wait_seconds": 0.25,
                        "agent_retry_max_wait_seconds": 4.0,
                        "agent_retry_backoff_multiplier": 2.0,
                        "agent_max_image_size_bytes": 5242880,
                        "agent_max_images_per_message": 4,
                        "agent_base_url": None,
                        "agent_api_key_configured": False,
                        "overrides": {"agent_model": "openai/gpt-4.1", "agent_api_key_configured": False},
                    }
                ).encode("utf-8"),
            ),
            HttpResponse(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "id": "run-1",
                        "thread_id": "thread-1",
                        "user_message_id": "msg-1",
                        "assistant_message_id": "msg-2",
                        "status": "completed",
                        "model_name": "openai/gpt-4.1",
                        "context_tokens": 32,
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "cache_read_tokens": None,
                        "cache_write_tokens": None,
                        "input_cost_usd": 0.1,
                        "output_cost_usd": 0.2,
                        "total_cost_usd": 0.3,
                        "error_text": None,
                        "created_at": "2026-03-08T00:00:00Z",
                        "completed_at": "2026-03-08T00:00:10Z",
                        "events": [],
                        "tool_calls": [],
                        "change_items": [],
                    }
                ).encode("utf-8"),
            ),
            HttpResponse(
                status_code=200,
                headers={},
                body=json.dumps(
                    {
                        "id": "run-1",
                        "thread_id": "thread-1",
                        "user_message_id": "msg-1",
                        "assistant_message_id": None,
                        "status": "running",
                        "model_name": "openai/gpt-4.1",
                        "context_tokens": 32,
                        "input_tokens": None,
                        "output_tokens": None,
                        "cache_read_tokens": None,
                        "cache_write_tokens": None,
                        "input_cost_usd": None,
                        "output_cost_usd": None,
                        "total_cost_usd": None,
                        "error_text": None,
                        "created_at": "2026-03-08T00:00:00Z",
                        "completed_at": None,
                        "events": [],
                        "tool_calls": [],
                        "change_items": [],
                    }
                ).encode("utf-8"),
            ),
        ]
    )

    def transport(request):
        requests.append(request)
        return next(responses)

    client = BillHelperApiClient(
        base_url="http://localhost:8000/api/v1",
        auth_headers={"X-Bill-Helper-Principal": "admin"},
        auth_token="secret-token",
        transport=transport,
    )

    threads = client.list_threads()
    created = client.create_thread(title="New thread")
    detail = client.get_thread("thread-1")
    settings = client.get_settings()
    updated = client.patch_settings(RuntimeSettingsUpdate(agent_model="openai/gpt-4.1"))
    fetched_run = client.get_run("run-1")
    run = client.interrupt_run("run-1")

    assert [thread.id for thread in threads] == ["thread-1"]
    assert created.id == "thread-2"
    assert detail.thread.id == "thread-1"
    assert settings.agent_model == "openrouter/qwen/qwen3.5-27b"
    assert updated.agent_model == "openai/gpt-4.1"
    assert fetched_run.status.value == "completed"
    assert run.id == "run-1"
    assert requests[0].url.endswith("/agent/threads")
    assert requests[1].url.endswith("/agent/threads")
    assert json.loads(requests[1].body.decode("utf-8")) == {"title": "New thread"}
    assert requests[2].url.endswith("/agent/threads/thread-1")
    assert requests[3].url.endswith("/settings")
    assert json.loads(requests[4].body.decode("utf-8")) == {"agent_model": "openai/gpt-4.1"}
    assert requests[5].url.endswith("/agent/runs/run-1?surface=telegram")
    assert requests[6].url.endswith("/agent/runs/run-1/interrupt")
    assert requests[0].headers["Authorization"] == "Bearer secret-token"
    assert requests[0].headers["X-Bill-Helper-Principal"] == "admin"


def test_send_thread_message_uses_backend_multipart_contract():
    requests = []

    def transport(request):
        requests.append(request)
        return HttpResponse(
            status_code=200,
            headers={},
            body=json.dumps(
                {
                    "id": "run-1",
                    "thread_id": "thread-1",
                    "user_message_id": "msg-1",
                    "assistant_message_id": None,
                    "status": "running",
                    "model_name": "openai/gpt-4.1",
                    "context_tokens": 16,
                    "input_tokens": None,
                    "output_tokens": None,
                    "cache_read_tokens": None,
                    "cache_write_tokens": None,
                    "input_cost_usd": None,
                    "output_cost_usd": None,
                    "total_cost_usd": None,
                    "error_text": None,
                    "created_at": "2026-03-08T00:00:00Z",
                    "completed_at": None,
                    "events": [],
                    "tool_calls": [],
                    "change_items": [],
                }
            ).encode("utf-8"),
        )

    client = BillHelperApiClient(base_url="http://localhost:8000/api/v1", transport=transport)
    run = client.send_thread_message(
        thread_id="thread-1",
        content="Please review this PDF.",
        files=[AttachmentUpload(filename="receipt.pdf", mime_type="application/pdf", content=b"pdf-bytes")],
    )

    body_text = requests[0].body.decode("utf-8")
    assert run.id == "run-1"
    assert requests[0].url.endswith("/agent/threads/thread-1/messages")
    assert requests[0].headers["Content-Type"].startswith("multipart/form-data; boundary=bill-helper-")
    assert 'name="content"' in body_text
    assert "Please review this PDF." in body_text
    assert 'name="surface"' in body_text
    assert "telegram" in body_text
    assert 'name="files"; filename="receipt.pdf"' in body_text
    assert "Content-Type: application/pdf" in body_text