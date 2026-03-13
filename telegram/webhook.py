# CALLING SPEC:
# - Purpose: provide Telegram integration behavior for `webhook`.
# - Inputs: callers that import `telegram/webhook.py` and pass module-defined arguments or framework events.
# - Outputs: Telegram handlers, models, or helpers exported by `webhook`.
# - Side effects: Telegram I/O and bot workflow integration as implemented below.
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import asynccontextmanager
import logging
from secrets import compare_digest

from fastapi import FastAPI, Header, HTTPException, status
import uvicorn

from telegram.commands import _register_bot_commands, build_application_from_settings
from telegram.config import TelegramSettings, get_settings
from telegram.ptb import Application, Update as PtbUpdate

LOGGER = logging.getLogger(__name__)
TELEGRAM_WEBHOOK_HEADER_NAME = "X-Telegram-Bot-Api-Secret-Token"
WEBHOOK_PATH = "/telegram/webhook"

type UpdateLoader = Callable[[Mapping[str, object], object], PtbUpdate]


def _validate_webhook_secret(expected_secret: str, provided_secret: str | None) -> bool:
    return compare_digest(expected_secret, provided_secret or "")


def _load_ptb_update(payload: Mapping[str, object], bot: object) -> PtbUpdate:
    return PtbUpdate.de_json(dict(payload), bot)


def create_app(
    settings: TelegramSettings | None = None,
    *,
    application: Application | None = None,
    update_loader: UpdateLoader = _load_ptb_update,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    if resolved_settings.webhook_secret is None:
        raise ValueError("TELEGRAM_WEBHOOK_SECRET is required to run the Telegram webhook.")

    resolved_settings.ensure_data_dir()
    ptb_application = application or build_application_from_settings(resolved_settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await ptb_application.initialize()
        await _register_bot_commands(ptb_application)
        await ptb_application.start()
        try:
            yield
        finally:
            await ptb_application.stop()
            await ptb_application.shutdown()

    app = FastAPI(title="Bill Helper Telegram Webhook", lifespan=lifespan)

    @app.get("/healthz")
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(WEBHOOK_PATH)
    async def receive_update(
        update_payload: dict[str, object],
        secret_token: str | None = Header(default=None, alias=TELEGRAM_WEBHOOK_HEADER_NAME),
    ) -> dict[str, bool]:
        if not _validate_webhook_secret(resolved_settings.webhook_secret, secret_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Telegram webhook secret.",
            )
        update = update_loader(update_payload, ptb_application.bot)
        await ptb_application.process_update(update)
        return {"ok": True}

    return app


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    app = create_app(get_settings())
    uvicorn.run(app, host="0.0.0.0", port=8081)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
