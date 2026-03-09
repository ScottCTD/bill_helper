from __future__ import annotations

from fastapi.routing import APIRoute

from backend.auth.contracts import PRINCIPAL_HEADER_NAME
from backend.auth.dependencies import get_or_create_current_principal
from backend.config import get_settings
from backend.main import create_app


def test_all_api_routes_require_request_principal_dependency() -> None:
    app = create_app()
    api_prefix = get_settings().api_prefix

    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith(api_prefix):
            continue
        dependency_calls = {
            dependency.call
            for dependency in route.dependant.dependencies
            if dependency.call is not None
        }
        if get_or_create_current_principal not in dependency_calls:
            methods = ",".join(sorted(route.methods or []))
            missing.append(f"{methods} {route.path}")

    assert missing == []


def test_protected_routes_require_explicit_principal_header(anonymous_client) -> None:
    response = anonymous_client.get("/api/v1/settings")

    assert response.status_code == 401
    assert response.json()["detail"] == f"Missing {PRINCIPAL_HEADER_NAME} header."
