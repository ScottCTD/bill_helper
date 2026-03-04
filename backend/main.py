from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routers import accounts, agent, currencies, dashboard, entities, entries, groups, links, settings, tags, taxonomies, users


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

    app.include_router(accounts.router, prefix=app_settings.api_prefix)
    app.include_router(currencies.router, prefix=app_settings.api_prefix)
    app.include_router(entities.router, prefix=app_settings.api_prefix)
    app.include_router(entries.router, prefix=app_settings.api_prefix)
    app.include_router(tags.router, prefix=app_settings.api_prefix)
    app.include_router(taxonomies.router, prefix=app_settings.api_prefix)
    app.include_router(users.router, prefix=app_settings.api_prefix)
    app.include_router(links.router, prefix=app_settings.api_prefix)
    app.include_router(groups.router, prefix=app_settings.api_prefix)
    app.include_router(dashboard.router, prefix=app_settings.api_prefix)
    app.include_router(agent.router, prefix=app_settings.api_prefix)
    app.include_router(settings.router, prefix=app_settings.api_prefix)

    return app


app = create_app()


def main() -> None:
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
