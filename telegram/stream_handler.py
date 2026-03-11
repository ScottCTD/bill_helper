from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from time import monotonic

from telegram.bill_helper_api import StreamEvent
from telegram.formatting import format_status_html, render_telegram_reply_chunks
from telegram.ptb import BadRequest, ChatAction, RetryAfter, TelegramError


@dataclass(slots=True)
class TelegramStreamConsumer:
    bot: object
    chat_id: int
    reply_to_message_id: int
    message_thread_id: int | None = None
    edit_interval_seconds: float = 1.5
    typing_interval_seconds: float = 4.0
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    sent_messages: list[object] = field(default_factory=list)
    assistant_text: str = ""
    run_id: str | None = None
    _last_rendered_chunks: list[str] = field(default_factory=list, init=False, repr=False)
    _last_edit_started_at: float = field(default=0.0, init=False, repr=False)
    _status_line: str | None = field(default=None, init=False, repr=False)
    _typing_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)

    async def start(self) -> object:
        if self._typing_task is None:
            self._typing_task = asyncio.create_task(self._typing_loop())
        placeholder = await self.bot.send_message(
            chat_id=self.chat_id,
            text=format_status_html("Working on it…"),
            parse_mode="HTML",
            reply_to_message_id=self.reply_to_message_id,
            message_thread_id=self.message_thread_id,
        )
        self.sent_messages.append(placeholder)
        self._last_rendered_chunks = [format_status_html("Working on it…")]
        return placeholder

    async def consume_event(self, event: StreamEvent) -> None:
        if event.run_id and self.run_id is None:
            self.run_id = event.run_id
        if event.event == "text_delta":
            delta = str(event.payload.get("delta") or "")
            if not delta:
                return
            self.assistant_text += delta
            await self._maybe_render_text()
            return
        if event.event == "run_event":
            run_event = event.payload.get("event")
            if not isinstance(run_event, dict):
                return
            if run_event.get("event_type") == "reasoning_update":
                message = str(run_event.get("message") or "").strip()
                if message:
                    self._status_line = message
                    if not self.assistant_text:
                        await self._render_status_message(message)

    async def finalize_reply(self, text: str) -> None:
        await self._stop_typing()
        chunks = render_telegram_reply_chunks(text)
        if not chunks:
            chunks = [format_status_html("Completed", "The run finished without a reply.")]
        await self._sync_chunks(chunks, force=True)

    async def finalize_error(self, title: str, body: str) -> None:
        await self._stop_typing()
        await self._sync_chunks([format_status_html(title, body)], force=True)

    async def close(self) -> None:
        await self._stop_typing()

    async def _maybe_render_text(self) -> None:
        now = monotonic()
        if now - self._last_edit_started_at < self.edit_interval_seconds:
            return
        await self._sync_chunks(render_telegram_reply_chunks(self.assistant_text))

    async def _render_status_message(self, message: str) -> None:
        await self._sync_chunks([format_status_html("Working on it…", message)], force=True)

    async def _sync_chunks(self, chunks: list[str], *, force: bool = False) -> None:
        if not chunks:
            return
        self._last_edit_started_at = monotonic()
        while len(self.sent_messages) < len(chunks):
            sent_message = await self.bot.send_message(
                chat_id=self.chat_id,
                text=chunks[len(self.sent_messages)],
                parse_mode="HTML",
                message_thread_id=self.message_thread_id,
            )
            self.sent_messages.append(sent_message)
        for index, chunk in enumerate(chunks):
            previous = self._last_rendered_chunks[index] if index < len(self._last_rendered_chunks) else None
            if not force and previous == chunk:
                continue
            message = self.sent_messages[index]
            if previous is None:
                continue
            await self._safe_edit_message(message.message_id, chunk)
        self._last_rendered_chunks = list(chunks)

    async def _safe_edit_message(self, message_id: int, text: str) -> None:
        try:
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
            )
        except BadRequest as exc:
            if "message is not modified" in str(exc).lower():
                return
            raise
        except RetryAfter as exc:
            await self.sleep(float(exc.retry_after))
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
            )

    async def _typing_loop(self) -> None:
        try:
            while True:
                try:
                    await self.bot.send_chat_action(
                        chat_id=self.chat_id,
                        action=ChatAction.TYPING,
                        message_thread_id=self.message_thread_id,
                    )
                except TelegramError:
                    pass
                await self.sleep(self.typing_interval_seconds)
        except asyncio.CancelledError:
            raise

    async def _stop_typing(self) -> None:
        if self._typing_task is None:
            return
        self._typing_task.cancel()
        try:
            await self._typing_task
        except asyncio.CancelledError:
            pass
        self._typing_task = None
