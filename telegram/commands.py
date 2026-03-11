from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from uuid import UUID

from backend.enums_agent import AgentRunStatus
from backend.schemas_agent import AgentRunRead, AgentThreadDetailRead, AgentThreadRead, AgentThreadSummaryRead
from telegram.charts import render_expense_by_filter_group, render_income_expense_trend
from telegram.bill_helper_api import BillHelperApiClient, BillHelperApiError
from telegram.config import TelegramSettings
from telegram.formatting import coerce_dashboard_month, format_dashboard_kpis_html, format_status_html
from telegram.message_handler import TelegramContentHandler
from telegram.ptb import (
    Application,
    ApplicationBuilder,
    BotCommand,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    Update as PtbUpdate,
    filters,
)
from telegram.review_handler import TelegramReviewHandler
from telegram.state import ChatStateStore
from telegram.ptb import Message as TelegramMessage

type TelegramMessageHandler = Callable[[TelegramMessage], Awaitable[object]]

PTB_ALLOWED_UPDATES = ["message", "callback_query"]
THREAD_SELECTOR_USAGE = "Usage: /use <number|thread-uuid>"
INVALID_THREAD_SELECTOR_REPLY = (
    f"{THREAD_SELECTOR_USAGE}\nThread selectors must be a positive list number or thread UUID."
)
UNAUTHORIZED_PRIVATE_REPLY = "This Telegram user is not authorized to use this bot."
TOPICS_USAGE = "Usage: /topics <on|off>"
TELEGRAM_BOT_COMMANDS = [
    BotCommand("start", "Introduction and quick help"),
    BotCommand("help", "List commands and supported uploads"),
    BotCommand("new", "Create a new conversation thread"),
    BotCommand("reset", "Start fresh without deleting old threads"),
    BotCommand("threads", "List recent threads"),
    BotCommand("use", "Switch to a thread by number or ID"),
    BotCommand("model", "Show or change the AI model"),
    BotCommand("stop", "Stop the current agent run"),
    BotCommand("status", "Show current model, thread, and run state"),
    BotCommand("dashboard", "Show dashboard charts for a month"),
    BotCommand("topics", "Toggle forum topics on or off"),
]


class TelegramCommandRouter:
    def __init__(
        self,
        *,
        api_client: BillHelperApiClient,
        state_store: ChatStateStore,
        max_listed_threads: int = 10,
    ) -> None:
        self._api_client = api_client
        self._state_store = state_store
        self._max_listed_threads = max_listed_threads

    def ensure_active_thread(self, chat_id: int) -> str:
        state = self._state_store.get(chat_id)
        if state is not None and state.active_thread_id:
            try:
                self._api_client.get_thread(state.active_thread_id)
                return state.active_thread_id
            except BillHelperApiError as exc:
                if exc.status_code != 404:
                    raise
                self._state_store.clear_chat(chat_id)

        created = self._api_client.create_thread()
        self._state_store.set_active_thread(chat_id, created.id)
        return created.id

    def resolve_active_run(self, chat_id: int) -> AgentRunRead | None:
        state = self._state_store.get(chat_id)
        if state is None or state.active_thread_id is None:
            return None
        if state.active_run_id:
            try:
                run = self._api_client.get_run(state.active_run_id)
            except BillHelperApiError as exc:
                if exc.status_code != 404:
                    raise
                self._state_store.clear_active_run(chat_id)
                return None
            if run.status != AgentRunStatus.RUNNING:
                self._state_store.clear_active_run(chat_id)
                return None
            return run

        detail = self._get_active_thread_detail(chat_id)
        if detail is None:
            return None
        for run in reversed(detail.runs):
            if run.status == AgentRunStatus.RUNNING:
                self._state_store.set_active_run(chat_id, run.id)
                return run
        return None

    def handle_start(self) -> str:
        return self._help_text(intro="Hi! I can manage Bill Helper threads and runs from Telegram.")

    def handle_help(self) -> str:
        return self._help_text()

    def handle_new(self, chat_id: int) -> str:
        created = self.create_new_thread(chat_id)
        return f"Started a new thread: {self._thread_label(created)} ({created.id})"

    def handle_reset(self, chat_id: int) -> str:
        created = self.create_new_thread(chat_id)
        return (
            f"Started a fresh thread: {self._thread_label(created)} ({created.id})\n"
            "Older threads are still available through /threads."
        )

    def handle_threads(self, chat_id: int) -> str:
        threads = self._api_client.list_threads()
        if not threads:
            return "No threads yet. Use /new or send a message to start one."

        state = self._state_store.get(chat_id)
        active_thread_id = state.active_thread_id if state is not None else None
        visible_threads = threads[: self._max_listed_threads]

        lines = ["Recent threads:"]
        for index, thread in enumerate(visible_threads, start=1):
            lines.append(self._format_thread_line(index=index, thread=thread, active_thread_id=active_thread_id))
        if len(threads) > len(visible_threads):
            lines.append(
                f"…and {len(threads) - len(visible_threads)} more. Use /use <thread-uuid> for older threads."
            )
        lines.append("Use /use <number|thread-uuid> to switch the active thread.")
        return "\n".join(lines)

    def handle_use(self, chat_id: int, selector: str | None) -> str:
        normalized_selector = (selector or "").strip()
        if not normalized_selector:
            return THREAD_SELECTOR_USAGE

        if normalized_selector.isdigit():
            index = int(normalized_selector)
            if index < 1:
                return INVALID_THREAD_SELECTOR_REPLY
            threads = self._api_client.list_threads()
            if index > len(threads):
                return f"Thread #{index} was not found. Use /threads to see the current list."
            detail = self._api_client.get_thread(threads[index - 1].id)
        else:
            thread_id = _normalize_thread_selector(normalized_selector)
            if thread_id is None:
                return INVALID_THREAD_SELECTOR_REPLY
            detail = self._api_client.get_thread(thread_id)

        self._state_store.set_active_thread(chat_id, detail.thread.id)
        return f"Switched to thread: {self._thread_label(detail.thread)} ({detail.thread.id})"

    def handle_model(self, requested_model: str | None) -> str:
        normalized_model = (requested_model or "").strip()
        settings = self._api_client.get_settings()
        if not normalized_model:
            return f"Current model: {settings.agent_model}\nUse /model <provider/model> to change it."

        matched_model, error_message = _resolve_model_selector(
            requested_model=normalized_model,
            available_models=settings.available_agent_models,
        )
        if error_message is not None:
            return error_message
        assert matched_model is not None
        updated = self._api_client.patch_settings({"agent_model": matched_model})
        return f"Updated model to {updated.agent_model}."

    def handle_stop(self, chat_id: int) -> str:
        active_run = self.resolve_active_run(chat_id)
        if active_run is None:
            return "No active run to stop."

        interrupted = self._api_client.interrupt_run(active_run.id)
        if interrupted.status == AgentRunStatus.RUNNING:
            self._state_store.set_active_run(chat_id, interrupted.id)
            return f"Run {interrupted.id} is still running."

        self._state_store.clear_active_run(chat_id)
        if interrupted.error_text:
            return f"Stopped run {interrupted.id}: {interrupted.error_text}"
        return f"Stopped run {interrupted.id}."

    def handle_status(self, chat_id: int) -> str:
        settings = self._api_client.get_settings()
        lines = [f"Model: {settings.agent_model}"]

        detail = self._get_active_thread_detail(chat_id)
        if detail is None:
            lines.append("Active thread: none")
            lines.append("Run: idle")
            return "\n".join(lines)

        lines.append(f"Active thread: {self._thread_label(detail.thread)} ({detail.thread.id})")
        active_run = self.resolve_active_run(chat_id)
        if active_run is None:
            lines.append("Run: idle")
        else:
            lines.append(f"Run: {active_run.status.value} ({active_run.id})")
        return "\n".join(lines)

    def create_new_thread(self, chat_id: int) -> AgentThreadRead:
        created = self._api_client.create_thread()
        self._state_store.set_active_thread(chat_id, created.id)
        return created

    def _get_active_thread_detail(self, chat_id: int) -> AgentThreadDetailRead | None:
        state = self._state_store.get(chat_id)
        if state is None or state.active_thread_id is None:
            return None
        try:
            return self._api_client.get_thread(state.active_thread_id)
        except BillHelperApiError as exc:
            if exc.status_code != 404:
                raise
            self._state_store.clear_chat(chat_id)
            return None

    def _format_thread_line(
        self,
        *,
        index: int,
        thread: AgentThreadSummaryRead,
        active_thread_id: str | None,
    ) -> str:
        flags: list[str] = []
        if thread.id == active_thread_id:
            flags.append("active")
        if thread.has_running_run:
            flags.append("running")
        suffix = f" [{' | '.join(flags)}]" if flags else ""
        return f"{index}. {self._thread_label(thread)}{suffix} — {thread.id}"

    def _help_text(self, *, intro: str | None = None) -> str:
        lines: list[str] = []
        if intro:
            lines.append(intro)
        lines.extend(
            [
                "Commands:",
                "/start — intro and quick help",
                "/help — show commands and supported file types",
                "/new — create and switch to a fresh thread",
                "/reset — start fresh without deleting older threads",
                "/threads — list recent threads",
                "/use <number|thread-uuid> — switch the active thread",
                "/model [provider/model|substring] — show or change the model",
                "/stop — interrupt the active run",
                "/status — show the active thread, model, and run state",
                "/dashboard [YYYY-MM] — show dashboard KPIs and charts",
                "/topics <on|off> — toggle Telegram forum topics",
                "Supported uploads: text, photos, image files, and PDFs.",
            ]
        )
        return "\n".join(lines)

    def _thread_label(self, thread: AgentThreadRead | AgentThreadSummaryRead | object) -> str:
        title = getattr(thread, "title", None)
        return title or "Untitled thread"


@dataclass(slots=True)
class TelegramBotHandlers:
    command_router: TelegramCommandRouter
    api_client: BillHelperApiClient | None = None
    state_store: ChatStateStore | None = None
    review_handler: TelegramReviewHandler | None = None
    message_handler: TelegramMessageHandler | None = None
    allowed_user_ids: frozenset[int] = frozenset()

    async def handle_start(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await self._reply_with(update, self.command_router.handle_start, needs_chat_id=False)

    async def handle_help(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await self._reply_with(update, self.command_router.handle_help, needs_chat_id=False)

    async def handle_new(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or chat.type != "private":
            return
        if not _is_allowed_private_user(update, self.allowed_user_ids):
            await message.reply_text(UNAUTHORIZED_PRIVATE_REPLY)
            return
        created = await asyncio.to_thread(self.command_router.create_new_thread, chat.id)
        await message.reply_text(f"Started a new thread: {created.title or 'Untitled thread'} ({created.id})")

    async def handle_reset(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await self._reply_with(update, self.command_router.handle_reset)

    async def handle_threads(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await self._reply_with(update, self.command_router.handle_threads)

    async def handle_use(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply_with(update, self.command_router.handle_use, " ".join(context.args).strip() or None)

    async def handle_model(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._reply_with(
            update,
            self.command_router.handle_model,
            " ".join(context.args).strip() or None,
            needs_chat_id=False,
        )

    async def handle_stop(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await self._reply_with(update, self.command_router.handle_stop)

    async def handle_status(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        await self._reply_with(update, self.command_router.handle_status)

    async def handle_dashboard(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or chat.type != "private" or self.api_client is None:
            return
        if not _is_allowed_private_user(update, self.allowed_user_ids):
            await message.reply_text(UNAUTHORIZED_PRIVATE_REPLY)
            return
        try:
            month = coerce_dashboard_month(context.args[0] if context.args else None)
        except ValueError as exc:
            await message.reply_html(format_status_html("Invalid month", str(exc)))
            return

        try:
            dashboard = await asyncio.to_thread(self.api_client.get_dashboard, month)
        except (BillHelperApiError, RuntimeError) as exc:
            await message.reply_html(format_status_html("Dashboard failed", str(exc)))
            return
        await message.reply_html(
            format_dashboard_kpis_html(
                month=dashboard.month,
                currency_code=dashboard.currency_code,
                kpis=dashboard.kpis,
            )
        )
        if dashboard.monthly_trend:
            trend_image = await asyncio.to_thread(
                partial(
                    render_income_expense_trend,
                    dashboard.monthly_trend,
                    currency_code=dashboard.currency_code,
                )
            )
            await message.reply_photo(photo=trend_image, caption="Income vs expense trend")
        if dashboard.filter_groups:
            group_image = await asyncio.to_thread(
                partial(
                    render_expense_by_filter_group,
                    dashboard.filter_groups,
                    currency_code=dashboard.currency_code,
                )
            )
            await message.reply_photo(photo=group_image, caption="Expense by filter group")
        if not dashboard.monthly_trend and not dashboard.filter_groups:
            await message.reply_html(format_status_html("Dashboard ready", "No chart data was available for that month."))

    async def handle_topics(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or chat.type != "private" or self.state_store is None:
            return
        if not _is_allowed_private_user(update, self.allowed_user_ids):
            await message.reply_text(UNAUTHORIZED_PRIVATE_REPLY)
            return
        argument = " ".join(context.args).strip().lower()
        if not argument:
            state = self.state_store.get(chat.id)
            enabled = bool(state.topics_enabled) if state is not None else False
            await message.reply_text(f"Topics are {'on' if enabled else 'off'}.")
            return
        if argument not in {"on", "off"}:
            await message.reply_text(TOPICS_USAGE)
            return
        enabled = argument == "on"
        self.state_store.set_topics_enabled(chat.id, enabled)
        if enabled:
            await message.reply_text(
                "Topics are on. Existing Telegram topics keep their own backend threads, and the first message in a new Telegram topic will bind a fresh backend thread. The bot will not create new Telegram topics for commands or /new."
            )
            return
        await message.reply_text("Topics are off. The bot will use the active flat-chat thread.")

    async def handle_content_message(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        del context
        message = update.effective_message
        if self.message_handler is None or message is None or not _is_private_chat(update):
            return
        if not _is_allowed_private_user(update, self.allowed_user_ids):
            await message.reply_text(UNAUTHORIZED_PRIVATE_REPLY)
            return
        await self.message_handler(message)

    async def handle_review_callback(self, update: PtbUpdate, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None or query.message is None or query.message.chat.type != "private":
            return
        if not _is_allowed_private_user(update, self.allowed_user_ids):
            await query.answer(UNAUTHORIZED_PRIVATE_REPLY, show_alert=True)
            return
        if self.review_handler is None:
            await query.answer("Review actions are unavailable.", show_alert=True)
            return
        try:
            await self.review_handler.handle_callback(update, context)
        except BillHelperApiError as exc:
            await query.answer(str(exc), show_alert=True)

    async def _reply_with(
        self,
        update: PtbUpdate,
        callback: Callable[..., str],
        *args: object,
        needs_chat_id: bool = True,
    ) -> None:
        message = update.effective_message
        chat = update.effective_chat
        if message is None or chat is None or chat.type != "private":
            return
        if not _is_allowed_private_user(update, self.allowed_user_ids):
            await message.reply_text(UNAUTHORIZED_PRIVATE_REPLY)
            return
        try:
            if needs_chat_id:
                reply = await asyncio.to_thread(callback, chat.id, *args)
            else:
                reply = await asyncio.to_thread(callback, *args)
        except (BillHelperApiError, RuntimeError) as exc:
            await message.reply_html(format_status_html("Request failed", str(exc)))
            return
        await message.reply_text(reply)


def register_application_handlers(application: Application, handlers: TelegramBotHandlers) -> Application:
    application.add_handler(CommandHandler("start", handlers.handle_start))
    application.add_handler(CommandHandler("help", handlers.handle_help))
    application.add_handler(CommandHandler("new", handlers.handle_new))
    application.add_handler(CommandHandler("reset", handlers.handle_reset))
    application.add_handler(CommandHandler("threads", handlers.handle_threads))
    application.add_handler(CommandHandler("use", handlers.handle_use))
    application.add_handler(CommandHandler("model", handlers.handle_model))
    application.add_handler(CommandHandler("stop", handlers.handle_stop))
    application.add_handler(CommandHandler("status", handlers.handle_status))
    application.add_handler(CommandHandler("dashboard", handlers.handle_dashboard))
    application.add_handler(CommandHandler("topics", handlers.handle_topics))
    application.add_handler(CallbackQueryHandler(handlers.handle_review_callback, pattern=r"^ci:"))
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ((filters.TEXT & ~filters.COMMAND) | filters.PHOTO | filters.Document.ALL),
            handlers.handle_content_message,
        )
    )
    return application


def build_handlers_from_settings(
    settings: TelegramSettings,
    *,
    bill_helper_api: BillHelperApiClient | None = None,
    state_store: ChatStateStore | None = None,
    message_handler: TelegramMessageHandler | None = None,
) -> TelegramBotHandlers:
    backend_client = bill_helper_api or BillHelperApiClient.from_settings(settings)
    chat_state_store = state_store or ChatStateStore.from_settings(settings)
    review_handler = TelegramReviewHandler(api_client=backend_client, state_store=chat_state_store)
    content_handler = message_handler or TelegramContentHandler(
        bill_helper_api=backend_client,
        state_store=chat_state_store,
        review_handler=review_handler,
    ).handle_message
    router = TelegramCommandRouter(api_client=backend_client, state_store=chat_state_store)
    return TelegramBotHandlers(
        command_router=router,
        api_client=backend_client,
        state_store=chat_state_store,
        review_handler=review_handler,
        message_handler=content_handler,
        allowed_user_ids=settings.allowed_user_ids,
    )


def build_application_from_settings(
    settings: TelegramSettings,
    *,
    bill_helper_api: BillHelperApiClient | None = None,
    state_store: ChatStateStore | None = None,
    message_handler: TelegramMessageHandler | None = None,
) -> Application:
    handlers = build_handlers_from_settings(
        settings,
        bill_helper_api=bill_helper_api,
        state_store=state_store,
        message_handler=message_handler,
    )
    application = ApplicationBuilder().token(settings.bot_token).post_init(_register_bot_commands).build()
    return register_application_handlers(application, handlers)


def _is_private_chat(update: PtbUpdate) -> bool:
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


def _is_allowed_private_user(update: PtbUpdate, allowed_user_ids: frozenset[int]) -> bool:
    user = update.effective_user
    if user is None or not allowed_user_ids:
        return False
    return user.id in allowed_user_ids


def _normalize_thread_selector(selector: str) -> str | None:
    if any(separator in selector for separator in ("/", "\\", "?", "#")) or ".." in selector:
        return None
    try:
        return str(UUID(selector))
    except ValueError:
        return None


async def _register_bot_commands(application: Application) -> None:
    await application.bot.set_my_commands(TELEGRAM_BOT_COMMANDS)


def _resolve_model_selector(*, requested_model: str, available_models: list[str]) -> tuple[str | None, str | None]:
    normalized_requested = requested_model.casefold()
    canonical_models = [model for model in available_models if _looks_like_model_identifier(model)]
    fallback_models = [model for model in available_models if not _looks_like_model_identifier(model)]

    if _looks_like_model_identifier(requested_model):
        exact_match = next(
            (model for model in available_models if model.casefold() == normalized_requested),
            None,
        )
        if exact_match is not None:
            return exact_match, None
    else:
        exact_canonical_match = next(
            (model for model in canonical_models if model.casefold() == normalized_requested),
            None,
        )
        if exact_canonical_match is not None:
            return exact_canonical_match, None

    matches = [model for model in canonical_models if normalized_requested in model.casefold()]
    if not matches and _looks_like_model_identifier(requested_model):
        matches = [model for model in fallback_models if normalized_requested in model.casefold()]
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, f"No model matched '{requested_model}'."
    match_lines = "\n".join(f"- {model}" for model in matches)
    return None, (
        f"Multiple models matched '{requested_model}'. Be more specific:\n"
        f"{match_lines}"
    )


def _looks_like_model_identifier(value: str) -> bool:
    return "/" in value
