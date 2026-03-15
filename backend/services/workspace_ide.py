# CALLING SPEC:
# - Purpose: implement focused service logic for `workspace_ide`.
# - Inputs: callers that import `backend/services/workspace_ide.py` and pass module-defined arguments or framework events.
# - Outputs: IDE launch helpers plus same-origin proxy header policy for the per-user workspace IDE.
# - Side effects: cookie mutation on FastAPI responses.
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from fastapi import Request, Response

from backend.config import Settings, get_settings
from backend.services.agent_workspace import (
    build_user_workspace_runtime,
    require_user_workspace_ide_host_port,
    start_user_workspace,
)
from backend.services.workspace_cli_env import refresh_workspace_cli_env

WORKSPACE_IDE_SESSION_COOKIE_NAME = "bill-helper.workspace-session"
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "content-encoding",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


@dataclass(slots=True, frozen=True)
class WorkspaceIdeLaunchView:
    launch_url: str


def workspace_ide_proxy_prefix(settings: Settings | None = None) -> str:
    resolved_settings = settings or get_settings()
    return f"{resolved_settings.api_prefix}/workspace/ide"


def launch_user_workspace_ide(
    *,
    user_id: str,
    request: Request,
    response: Response,
    session_token: str,
    settings: Settings | None = None,
) -> WorkspaceIdeLaunchView:
    start_user_workspace(user_id=user_id, settings=settings)
    refresh_workspace_cli_env(
        user_id=user_id,
        session_token=session_token,
        settings=settings,
    )
    runtime = build_user_workspace_runtime(user_id=user_id, settings=settings)
    if runtime.status != "running" or not runtime.ide_ready:
        detail = runtime.degraded_reason or "Workspace IDE is unavailable."
        from backend.services.crud_policy import PolicyViolation

        raise PolicyViolation(detail=detail, status_code=503)
    set_workspace_ide_session_cookie(
        response=response,
        request=request,
        session_token=session_token,
        settings=settings,
    )
    folder = quote("/workspace", safe="/")
    return WorkspaceIdeLaunchView(launch_url=f"{runtime.ide_launch_path}?folder={folder}")


def workspace_ide_target_http_url(
    *,
    user_id: str,
    path: str,
    query_string: str,
    settings: Settings | None = None,
) -> str:
    host_port = require_user_workspace_ide_host_port(user_id=user_id, settings=settings)
    normalized_path = path.lstrip("/")
    suffix = f"/{normalized_path}" if normalized_path else "/"
    query_suffix = f"?{query_string}" if query_string else ""
    return f"http://127.0.0.1:{host_port}{suffix}{query_suffix}"


def workspace_ide_target_ws_url(
    *,
    user_id: str,
    path: str,
    query_string: str,
    settings: Settings | None = None,
) -> str:
    host_port = require_user_workspace_ide_host_port(user_id=user_id, settings=settings)
    normalized_path = path.lstrip("/")
    suffix = f"/{normalized_path}" if normalized_path else "/"
    query_suffix = f"?{query_string}" if query_string else ""
    return f"ws://127.0.0.1:{host_port}{suffix}{query_suffix}"


def set_workspace_ide_session_cookie(
    *,
    response: Response,
    request: Request,
    session_token: str,
    settings: Settings | None = None,
) -> None:
    response.set_cookie(
        key=WORKSPACE_IDE_SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path=f"{workspace_ide_proxy_prefix(settings)}/",
    )


def clear_workspace_ide_session_cookie(
    *,
    response: Response,
    settings: Settings | None = None,
) -> None:
    response.delete_cookie(
        key=WORKSPACE_IDE_SESSION_COOKIE_NAME,
        path=f"{workspace_ide_proxy_prefix(settings)}/",
    )


def filter_workspace_proxy_request_headers(headers: dict[str, str]) -> dict[str, str]:
    filtered_headers = {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "cookie"
    }
    filtered_headers["accept-encoding"] = "identity"
    return filtered_headers


def filter_workspace_proxy_response_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS and key.lower() != "set-cookie"
    }
