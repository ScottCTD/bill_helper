from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.routers import accounts, agent, currencies, dashboard, entities, entries, groups, links, tags, taxonomies, users


def create_app() -> FastAPI:
    settings = get_settings()
    Path(".data").mkdir(exist_ok=True)

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(accounts.router, prefix=settings.api_prefix)
    app.include_router(currencies.router, prefix=settings.api_prefix)
    app.include_router(entities.router, prefix=settings.api_prefix)
    app.include_router(entries.router, prefix=settings.api_prefix)
    app.include_router(tags.router, prefix=settings.api_prefix)
    app.include_router(taxonomies.router, prefix=settings.api_prefix)
    app.include_router(users.router, prefix=settings.api_prefix)
    app.include_router(links.router, prefix=settings.api_prefix)
    app.include_router(groups.router, prefix=settings.api_prefix)
    app.include_router(dashboard.router, prefix=settings.api_prefix)
    app.include_router(agent.router, prefix=settings.api_prefix)

    return app


app = create_app()


def main() -> None:
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
