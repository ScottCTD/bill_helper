from __future__ import annotations

from fastapi.routing import APIRoute

from backend.auth.dependencies import get_current_auth_context, get_current_principal
from backend.config import get_settings
from backend.main import create_app


def test_all_api_routes_require_request_principal_dependency() -> None:
    app = create_app()
    api_prefix = get_settings().api_prefix
    workspace_cookie_dependency_name = "get_current_principal_from_cookie.<locals>._dependency"

    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith(api_prefix):
            continue
        if route.path.startswith(f"{api_prefix}/auth"):
            continue
        dependency_calls = {
            dependency.call
            for dependency in route.dependant.dependencies
            if dependency.call is not None
        }
        dependency_names = {getattr(call, "__qualname__", "") for call in dependency_calls}
        has_workspace_cookie_dependency = workspace_cookie_dependency_name in dependency_names
        has_bearer_auth_context = get_current_auth_context in dependency_calls
        if get_current_principal not in dependency_calls and not has_workspace_cookie_dependency and not has_bearer_auth_context:
            methods = ",".join(sorted(route.methods or []))
            missing.append(f"{methods} {route.path}")

    assert missing == []


def test_protected_routes_require_bearer_authorization_header(anonymous_client) -> None:
    response = anonymous_client.get("/api/v1/settings")

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header."
