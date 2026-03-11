from __future__ import annotations

from importlib import metadata
from pathlib import Path
import sys


def _bootstrap_python_telegram_bot() -> None:
    package = sys.modules[__package__]
    if getattr(package, "_bill_helper_ptb_bootstrapped", False):
        return

    try:
        distribution = metadata.distribution("python-telegram-bot")
    except metadata.PackageNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "python-telegram-bot is required for Telegram integration. Install it with `uv add python-telegram-bot`."
        ) from exc

    ptb_dir = Path(distribution.locate_file("telegram")).resolve()
    ptb_init = ptb_dir / "__init__.py"
    package_path = package.__dict__.setdefault("__path__", [])
    if str(ptb_dir) not in package_path:
        package_path.append(str(ptb_dir))
    package.__dict__["__file__"] = str(ptb_init)
    package.__dict__["__package__"] = "telegram"
    exec(compile(ptb_init.read_text(encoding="utf-8"), str(ptb_init), "exec"), package.__dict__)
    package._bill_helper_ptb_bootstrapped = True


_bootstrap_python_telegram_bot()

from telegram import (  # noqa: E402
    Bot,
    BotCommand,
    CallbackQuery,
    Document,
    File,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    PhotoSize,
    Update,
)
from telegram.constants import ChatAction, ParseMode  # noqa: E402
from telegram.error import BadRequest, RetryAfter, TelegramError  # noqa: E402
from telegram.ext import (  # noqa: E402
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

__all__ = [
    "Application",
    "ApplicationBuilder",
    "BadRequest",
    "Bot",
    "BotCommand",
    "CallbackQuery",
    "CallbackQueryHandler",
    "ChatAction",
    "CommandHandler",
    "ContextTypes",
    "Document",
    "File",
    "InlineKeyboardButton",
    "InlineKeyboardMarkup",
    "Message",
    "MessageHandler",
    "ParseMode",
    "PhotoSize",
    "RetryAfter",
    "TelegramError",
    "Update",
    "filters",
]
