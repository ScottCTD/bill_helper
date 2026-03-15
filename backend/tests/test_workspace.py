from __future__ import annotations

import asyncio

from backend.config import get_settings
from backend.database import get_session_maker
from backend.routers import workspace as workspace_router
from backend.schemas_workspace import WorkspaceSnapshotRead
from backend.services.workspace_ide import (
    WORKSPACE_IDE_SESSION_COOKIE_NAME,
    WorkspaceIdeLaunchView,
    filter_workspace_proxy_request_headers,
)
from backend.services.user_files import (
    SOURCE_TYPE_AGENT_ATTACHMENT,
    STORAGE_AREA_UPLOAD,
    store_user_file_bytes,
)
from backend.services.users import find_user_by_name
from backend.services.workspace_browser import build_user_workspace_snapshot


def test_workspace_snapshot_returns_disabled_status(client) -> None:
    db = get_session_maker()()
    try:
        admin = find_user_by_name(db, "admin")
        assert admin is not None
        store_user_file_bytes(
            db,
            owner_user_id=admin.id,
            storage_area=STORAGE_AREA_UPLOAD,
            source_type=SOURCE_TYPE_AGENT_ATTACHMENT,
            mime_type="text/plain",
            file_bytes=b"hello workspace",
            original_filename="family-photo.jpg",
            stored_filename="02bf89bc-c2a4-46ed-a163-466b7437f2d1.jpg",
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/workspace")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_enabled"] is False
    assert payload["starts_on_login"] is False
    assert payload["status"] == "disabled"
    assert payload["ide_ready"] is False
    assert payload["ide_launch_path"] == "/api/v1/workspace/ide/"
    assert "disabled" in payload["degraded_reason"].lower()


def test_workspace_proxy_rejects_missing_cookie(client) -> None:
    response = client.get("/api/v1/workspace/ide")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing workspace session cookie."


def test_workspace_proxy_request_headers_force_identity_encoding() -> None:
    headers = filter_workspace_proxy_request_headers(
        {
            "accept": "text/html",
            "accept-encoding": "gzip, deflate, br, zstd",
            "cookie": "workspace=secret",
            "host": "127.0.0.1:8000",
            "user-agent": "playwright",
        }
    )

    assert headers["accept"] == "text/html"
    assert headers["accept-encoding"] == "identity"
    assert headers["user-agent"] == "playwright"
    assert "cookie" not in headers
    assert "host" not in headers


def test_safe_websocket_close_ignores_closed_socket_runtime_error() -> None:
    class ClosedWebSocket:
        async def close(self, *, code: int = 1000, reason: str | None = None) -> None:
            raise RuntimeError("Unexpected ASGI message 'websocket.close'")

    asyncio.run(
        workspace_router._safe_websocket_close(  # noqa: SLF001
            ClosedWebSocket(),
            code=1013,
            reason="Workspace IDE unavailable",
        )
    )


def test_upstream_close_code_normalizes_reserved_disconnect_codes() -> None:
    assert workspace_router._upstream_close_code(1005) == 1000  # noqa: SLF001
    assert workspace_router._upstream_close_code(1006) == 1000  # noqa: SLF001
    assert workspace_router._upstream_close_code(1015) == 1000  # noqa: SLF001
    assert workspace_router._upstream_close_code(1001) == 1001  # noqa: SLF001
    assert workspace_router._upstream_close_code("1001") == 1000  # noqa: SLF001


def test_workspace_ide_session_sets_workspace_cookie(client, monkeypatch) -> None:
    snapshot = WorkspaceSnapshotRead(
        workspace_enabled=True,
        starts_on_login=True,
        status="running",
        container_name="bill-helper-sandbox-user-1",
        volume_name="bill-helper-workspace-user-1",
        ide_ready=True,
        ide_launch_path="/api/v1/workspace/ide/",
        degraded_reason=None,
    )

    def fake_launch_user_workspace_ide(**kwargs):
        kwargs["response"].set_cookie(
            WORKSPACE_IDE_SESSION_COOKIE_NAME,
            "test-session-token",
            path="/api/v1/workspace/ide/",
        )
        return WorkspaceIdeLaunchView(launch_url="/api/v1/workspace/ide/?folder=/workspace")

    monkeypatch.setattr(
        workspace_router,
        "launch_user_workspace_ide",
        fake_launch_user_workspace_ide,
    )
    monkeypatch.setattr(
        workspace_router,
        "_workspace_snapshot_response",
        lambda **_: snapshot,
    )

    response = client.post("/api/v1/workspace/ide/session")

    assert response.status_code == 200
    assert response.json()["launch_url"] == "/api/v1/workspace/ide/?folder=/workspace"
    assert response.json()["snapshot"]["ide_ready"] is True
    assert WORKSPACE_IDE_SESSION_COOKIE_NAME in response.headers.get("set-cookie", "")


def test_start_and_stop_workspace_endpoints_are_noops_when_workspace_is_disabled(client) -> None:
    start_response = client.post("/api/v1/workspace/start")
    stop_response = client.post("/api/v1/workspace/stop")

    assert start_response.status_code == 200
    assert stop_response.status_code == 200
    assert start_response.json()["status"] == "disabled"
    assert stop_response.json()["status"] == "disabled"


def test_workspace_snapshot_reports_missing_image_without_raising(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("BILL_HELPER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_ENABLED", "1")
    monkeypatch.setenv("BILL_HELPER_AGENT_WORKSPACE_IMAGE", "missing:test-image")
    get_settings.cache_clear()
    try:
        snapshot = build_user_workspace_snapshot(user_id="user-1")
    finally:
        get_settings.cache_clear()

    assert snapshot.workspace_enabled is True
    assert snapshot.starts_on_login is True
    assert snapshot.status == "image_missing"
    assert snapshot.ide_ready is False
    assert snapshot.ide_launch_path == "/api/v1/workspace/ide/"
    assert snapshot.degraded_reason is not None
    assert "missing" in snapshot.degraded_reason.lower()
