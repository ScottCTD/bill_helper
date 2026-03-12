from __future__ import annotations

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.auth.dependencies import get_current_principal
from backend.config import get_settings
from backend.routers import (
    admin,
    auth,
    currencies,
    dashboard,
    entities,
    entries,
    filter_groups,
    groups,
    settings,
    tags,
    taxonomies,
    users,
)
from backend.routers.agent import router as agent_router
from backend.routers.accounts import router as accounts_router
from backend.services.crud_policy import PolicyViolation


def create_app() -> FastAPI:
    app_settings = get_settings()
    app_settings.ensure_data_dir()

    app = FastAPI(title=app_settings.app_name)

    @app.exception_handler(PolicyViolation)
    def handle_policy_violation(_request: Request, error: PolicyViolation) -> JSONResponse:
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    app.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(auth.router, prefix=app_settings.api_prefix)

    protected_dependencies = [Depends(get_current_principal)]
    protected_routers = (
        admin.router,
        accounts_router,
        currencies.router,
        entities.router,
        entries.router,
        tags.router,
        filter_groups.router,
        taxonomies.router,
        users.router,
        groups.router,
        dashboard.router,
        agent_router,
        settings.router,
    )
    for router in protected_routers:
        app.include_router(
            router,
            prefix=app_settings.api_prefix,
            dependencies=protected_dependencies,
        )

    return app


def main() -> None:
    uvicorn.run("backend.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True)


if __name__ == "__main__":
    main()
