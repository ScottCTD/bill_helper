# CALLING SPEC:
# - Purpose: translate HTTP and websocket requests for `workspace` routes.
# - Inputs: callers that import `backend/routers/workspace.py` and pass module-defined arguments or framework events.
# - Outputs: router callables and request/response adapters for workspace lifecycle, IDE launch, and IDE proxying.
# - Side effects: FastAPI routing, cookie mutation, Docker-backed workspace lifecycle calls, and local reverse proxy traffic.
from __future__ import annotations

import anyio
import logging
from fastapi import APIRouter, Depends, Request, Response, WebSocket
from fastapi.responses import Response as FastAPIResponse
import httpx
import websockets

from backend.auth.contracts import AuthenticatedSessionContext, RequestPrincipal
from backend.auth.dependencies import (
    get_current_auth_context,
    get_current_principal,
    get_current_principal_from_cookie,
)
from backend.schemas_workspace import WorkspaceIdeSessionRead, WorkspaceSnapshotRead
from backend.services.agent_workspace import start_user_workspace, stop_user_workspace
from backend.services.workspace_browser import build_user_workspace_snapshot
from backend.services.workspace_ide import (
    WORKSPACE_IDE_SESSION_COOKIE_NAME,
    clear_workspace_ide_session_cookie,
    filter_workspace_proxy_request_headers,
    filter_workspace_proxy_response_headers,
    launch_user_workspace_ide,
    workspace_ide_target_http_url,
    workspace_ide_target_ws_url,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])
workspace_cookie_principal = get_current_principal_from_cookie(WORKSPACE_IDE_SESSION_COOKIE_NAME)
PROXIED_HTTP_METHODS = ("DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT")
logger = logging.getLogger(__name__)


@router.get("", response_model=WorkspaceSnapshotRead)
def get_workspace_snapshot(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> WorkspaceSnapshotRead:
    return _workspace_snapshot_response(user_id=principal.user_id)


@router.post("/start", response_model=WorkspaceSnapshotRead)
def start_workspace(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> WorkspaceSnapshotRead:
    start_user_workspace(user_id=principal.user_id)
    return _workspace_snapshot_response(user_id=principal.user_id)


@router.post("/stop", response_model=WorkspaceSnapshotRead)
def stop_workspace(
    principal: RequestPrincipal = Depends(get_current_principal),
) -> WorkspaceSnapshotRead:
    stop_user_workspace(user_id=principal.user_id)
    return _workspace_snapshot_response(user_id=principal.user_id)


@router.post("/ide/session", response_model=WorkspaceIdeSessionRead)
def create_workspace_ide_session(
    request: Request,
    response: Response,
    auth_context: AuthenticatedSessionContext = Depends(get_current_auth_context),
) -> WorkspaceIdeSessionRead:
    launch = launch_user_workspace_ide(
        user_id=auth_context.principal.user_id,
        request=request,
        response=response,
        session_token=auth_context.session_token,
    )
    snapshot = _workspace_snapshot_response(user_id=auth_context.principal.user_id)
    return WorkspaceIdeSessionRead(launch_url=launch.launch_url, snapshot=snapshot)


@router.api_route("/ide", methods=PROXIED_HTTP_METHODS, include_in_schema=False)
@router.api_route("/ide/{path:path}", methods=PROXIED_HTTP_METHODS, include_in_schema=False)
async def proxy_workspace_ide_http(
    request: Request,
    path: str = "",
    principal: RequestPrincipal = Depends(workspace_cookie_principal),
) -> FastAPIResponse:
    query_string = request.url.query
    target_url = workspace_ide_target_http_url(
        user_id=principal.user_id,
        path=path,
        query_string=query_string,
    )
    headers = filter_workspace_proxy_request_headers(dict(request.headers.items()))
    body = await request.body()
    async with httpx.AsyncClient(follow_redirects=False, timeout=120.0) as client:
        upstream = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
        )
    response_headers = filter_workspace_proxy_response_headers(dict(upstream.headers.items()))
    media_type = upstream.headers.get("content-type")
    return FastAPIResponse(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=response_headers,
        media_type=media_type,
    )


@router.websocket("/ide")
@router.websocket("/ide/{path:path}")
async def proxy_workspace_ide_websocket(
    websocket: WebSocket,
    path: str = "",
    principal: RequestPrincipal = Depends(workspace_cookie_principal),
) -> None:
    query_bytes = websocket.scope.get("query_string", b"")
    query_string = query_bytes.decode("utf-8") if isinstance(query_bytes, bytes) else ""
    target_url = workspace_ide_target_ws_url(
        user_id=principal.user_id,
        path=path,
        query_string=query_string,
    )
    requested_subprotocols = _requested_subprotocols(websocket.headers.get("sec-websocket-protocol"))
    connect_kwargs: dict[str, object] = {
        "open_timeout": 15,
    }
    if requested_subprotocols:
        connect_kwargs["subprotocols"] = requested_subprotocols
    try:
        async with websockets.connect(target_url, **connect_kwargs) as upstream:
            await websocket.accept(subprotocol=upstream.subprotocol)

            async with anyio.create_task_group() as task_group:
                async def forward_client_messages() -> None:
                    try:
                        while True:
                            message = await websocket.receive()
                            message_type = message.get("type")
                            if message_type == "websocket.disconnect":
                                await upstream.close(code=_upstream_close_code(message.get("code")))
                                break
                            text_payload = message.get("text")
                            if isinstance(text_payload, str):
                                await upstream.send(text_payload)
                                continue
                            bytes_payload = message.get("bytes")
                            if isinstance(bytes_payload, bytes):
                                await upstream.send(bytes_payload)
                    finally:
                        task_group.cancel_scope.cancel()

                async def forward_upstream_messages() -> None:
                    try:
                        while True:
                            message = await upstream.recv()
                            try:
                                if isinstance(message, bytes):
                                    await websocket.send_bytes(message)
                                else:
                                    await websocket.send_text(message)
                            except RuntimeError:
                                await upstream.close()
                                break
                    except websockets.ConnectionClosed as error:
                        await _safe_websocket_close(websocket, code=error.code or 1000)
                    finally:
                        task_group.cancel_scope.cancel()

                task_group.start_soon(forward_client_messages)
                task_group.start_soon(forward_upstream_messages)
    except websockets.ConnectionClosed:
        await _safe_websocket_close(websocket, code=1000)
    except Exception:
        logger.exception(
            "Workspace IDE websocket proxy failed for user %s on path %s",
            principal.user_id,
            path or "/",
        )
        await _safe_websocket_close(websocket, code=1013, reason="Workspace IDE unavailable")


def _workspace_snapshot_response(*, user_id: str) -> WorkspaceSnapshotRead:
    return WorkspaceSnapshotRead.model_validate(
        build_user_workspace_snapshot(user_id=user_id),
        from_attributes=True,
    )


def _requested_subprotocols(raw_header: str | None) -> list[str]:
    if raw_header is None:
        return []
    return [part.strip() for part in raw_header.split(",") if part.strip()]


def _upstream_close_code(raw_code: object) -> int:
    if not isinstance(raw_code, int):
        return 1000
    if raw_code < 1000 or raw_code >= 5000:
        return 1000
    if raw_code in {1004, 1005, 1006, 1015}:
        return 1000
    return raw_code


async def _safe_websocket_close(
    websocket: WebSocket,
    *,
    code: int = 1000,
    reason: str | None = None,
) -> None:
    try:
        await websocket.close(code=_upstream_close_code(code), reason=reason)
    except RuntimeError:
        return


def clear_workspace_cookie_on_logout(response: Response) -> None:
    clear_workspace_ide_session_cookie(response=response)
