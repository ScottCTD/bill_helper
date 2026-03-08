from __future__ import annotations

import uvicorn
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.auth import get_current_principal
from backend.config import get_settings
from backend.routers import currencies, dashboard, entities, entries, groups, settings, tags, taxonomies, users
from backend.routers.agent import router as agent_router
from backend.routers.accounts import router as accounts_router


def create_app() -> FastAPI:
    app_settings = get_settings()
    app_settings.ensure_data_dir()

    app = FastAPI(title=app_settings.app_name)

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

    protected_dependencies = [Depends(get_current_principal)]
    protected_routers = (
        accounts_router,
        currencies.router,
        entities.router,
        entries.router,
        tags.router,
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
