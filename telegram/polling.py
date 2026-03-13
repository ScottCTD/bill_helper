# CALLING SPEC:
# - Purpose: provide Telegram integration behavior for `polling`.
# - Inputs: callers that import `telegram/polling.py` and pass module-defined arguments or framework events.
# - Outputs: Telegram handlers, models, or helpers exported by `polling`.
# - Side effects: Telegram I/O and bot workflow integration as implemented below.
from __future__ import annotations

import logging

from telegram.commands import PTB_ALLOWED_UPDATES, build_application_from_settings
from telegram.config import get_settings
from telegram.ptb import Application

LOGGER = logging.getLogger(__name__)


def run_polling(*, application: Application, drop_pending_updates: bool = False) -> None:
    application.run_polling(
        allowed_updates=PTB_ALLOWED_UPDATES,
        drop_pending_updates=drop_pending_updates,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    settings.ensure_data_dir()
    application = build_application_from_settings(settings)
    try:
        run_polling(application=application)
    except KeyboardInterrupt:
        LOGGER.info("Telegram polling stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())