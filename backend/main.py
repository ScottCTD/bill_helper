# CALLING SPEC:
# - Purpose: provide the `main` module.
# - Inputs: callers that import `backend/main.py` and pass module-defined arguments or framework events.
# - Outputs: module exports from `main`.
# - Side effects: module-local behavior only.
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
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
    workspace,
)
from backend.routers.agent import router as agent_router
from backend.routers.accounts import router as accounts_router
from backend.services.crud_policy import PolicyViolation
from backend.services.agent_workspace import stop_all_user_workspaces_best_effort

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _app_lifespan(_app: FastAPI):
    try:
        yield
    finally:
        try:
            stop_all_user_workspaces_best_effort()
        except Exception:
            logger.exception("Workspace shutdown sweep crashed during app shutdown")


def create_app() -> FastAPI:
    app_settings = get_settings()
    app_settings.ensure_data_dir()

    app = FastAPI(title=app_settings.app_name, lifespan=_app_lifespan)

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
    app.include_router(workspace.router, prefix=app_settings.api_prefix)

    return app


def main() -> None:
    uvicorn.run("backend.main:create_app", host="0.0.0.0", port=8000, reload=True, factory=True)


if __name__ == "__main__":
    main()
