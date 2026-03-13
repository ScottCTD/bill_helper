# CALLING SPEC:
# - Purpose: provide Telegram integration behavior for `message_handler`.
# - Inputs: callers that import `telegram/message_handler.py` and pass module-defined arguments or framework events.
# - Outputs: Telegram handlers, models, or helpers exported by `message_handler`.
# - Side effects: Telegram I/O and bot workflow integration as implemented below.
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from backend.schemas_agent import AgentMessageRead, AgentRunRead
from telegram.bill_helper_api import BillHelperApiClient, BillHelperApiError, BillHelperApiStreamError
from telegram.files import TelegramAttachmentError, download_message_attachments
from telegram.formatting import (
    format_run_cost_footer,
    format_status_html,
    render_telegram_reply_chunks,
    simplify_markdown_for_telegram,
)
from telegram.ptb import Message as TelegramMessage
from telegram.ptb import BadRequest
from telegram.review_handler import TelegramReviewHandler
from telegram.state import ChatStateStore
from telegram.stream_handler import TelegramStreamConsumer


@dataclass(slots=True)
class TelegramContentHandler:
    bill_helper_api: BillHelperApiClient
    state_store: ChatStateStore
    review_handler: TelegramReviewHandler | None = None
    poll_interval_seconds: float = 1.0
    max_polls: int = 120
    stream_edit_interval_seconds: float = 1.5
    typing_interval_seconds: float = 4.0
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    telegram_api: object | None = None

    async def handle_message(self, message: TelegramMessage) -> list[TelegramMessage]:
        chat_id = message.chat_id
        message_thread_id = getattr(message, "message_thread_id", None)
        bot = message.get_bot()
        consumer: TelegramStreamConsumer | None = None

        try:
            thread_id = await self._resolve_target_thread(chat_id, message_thread_id)
            settings = await asyncio.to_thread(self.bill_helper_api.get_settings)
            async with download_message_attachments(
                message=message,
                max_size_bytes=settings.agent_max_image_size_bytes,
                max_attachments=settings.agent_max_images_per_message,
            ) as attachments:
                content = (message.text or message.caption or "").strip()
                if not content and not attachments:
                    return [
                        await message.reply_html(
                            format_status_html(
                                "Nothing to send",
                                "Send text, a photo, an image document, or a PDF.",
                            )
                        )
                    ]
                consumer = TelegramStreamConsumer(
                    bot=bot,
                    chat_id=chat_id,
                    reply_to_message_id=message.message_id,
                    message_thread_id=message_thread_id,
                    edit_interval_seconds=self.stream_edit_interval_seconds,
                    typing_interval_seconds=self.typing_interval_seconds,
                    sleep=self.sleep,
                )
                await consumer.start()
                run = await self._stream_or_poll_run(
                    chat_id=chat_id,
                    thread_id=thread_id,
                    content=content,
                    attachments=[attachment.to_upload() for attachment in attachments],
                    consumer=consumer,
                )
        except TelegramAttachmentError as exc:
            return [
                await message.reply_html(format_status_html("Attachment rejected", str(exc)))
            ]
        except (BillHelperApiError, RuntimeError, TimeoutError) as exc:
            if consumer is not None:
                await consumer.finalize_error("Bill Helper request failed", str(exc))
                return consumer.sent_messages
            return [
                await message.reply_html(format_status_html("Bill Helper request failed", str(exc)))
            ]

        try:
            sent_messages = await self._deliver_terminal_reply(
                message=message,
                run=run,
                consumer=consumer,
            )
            await self._sync_topic_name(chat_id=chat_id, thread_id=run.thread_id, bot=bot)
            if self.review_handler is not None and run.status.value == "completed":
                sent_messages.extend(
                    await self.review_handler.render_change_items(
                        bot=bot,
                        chat_id=chat_id,
                        run=run,
                        message_thread_id=message_thread_id,
                    )
                )
            return sent_messages
        finally:
            self.state_store.clear_active_run(chat_id)

    async def poll_run_until_terminal(self, run_id: str, *, seed_run: AgentRunRead | None = None) -> AgentRunRead:
        run = seed_run or await asyncio.to_thread(self.bill_helper_api.get_run, run_id)
        polls = 0
        while run.status.value == "running":
            if polls >= self.max_polls:
                raise TimeoutError(f"Timed out waiting for run {run_id}")
            await self.sleep(self.poll_interval_seconds)
            run = await asyncio.to_thread(self.bill_helper_api.get_run, run_id)
            polls += 1
        return run

    async def _deliver_terminal_reply(
        self,
        *,
        message: TelegramMessage,
        run: AgentRunRead,
        consumer: TelegramStreamConsumer | None,
    ) -> list[TelegramMessage]:
        if run.status.value != "completed":
            error_text = (run.error_text or "The request did not complete.").strip()
            if consumer is not None:
                await consumer.finalize_error("Request failed", error_text)
                return consumer.sent_messages
            return [await message.reply_html(format_status_html("Request failed", error_text))]

        final_reply = await self._resolve_final_reply(run)
        footer = format_run_cost_footer(run)
        reply_text = final_reply or "The run completed, but no final reply was returned."
        if footer:
            reply_text = f"{reply_text}\n\n{footer}"
        if consumer is not None:
            await consumer.finalize_reply(reply_text)
            return consumer.sent_messages
        sent_messages: list[TelegramMessage] = []
        for chunk in render_telegram_reply_chunks(reply_text):
            sent_messages.append(await message.reply_html(chunk))
        return sent_messages

    async def _ensure_active_thread(self, chat_id: int) -> str:
        state = self.state_store.get(chat_id)
        if state is not None and state.active_thread_id:
            return state.active_thread_id
        thread = await asyncio.to_thread(self.bill_helper_api.create_thread)
        self.state_store.set_active_thread(chat_id, thread.id)
        return thread.id

    async def _resolve_final_reply(self, run: AgentRunRead) -> str | None:
        reply = (run.terminal_assistant_reply or "").strip()
        if reply:
            return reply
        if not run.assistant_message_id:
            return None
        detail = await asyncio.to_thread(self.bill_helper_api.get_thread, run.thread_id)
        assistant_message = next(
            (message for message in reversed(detail.messages) if message.id == run.assistant_message_id),
            None,
        )
        return self._fallback_message_reply(assistant_message)

    def _fallback_message_reply(self, message: AgentMessageRead | None) -> str | None:
        content = simplify_markdown_for_telegram(message.content_markdown if message is not None else None)
        return content or None

    async def _stream_or_poll_run(
        self,
        *,
        chat_id: int,
        thread_id: str,
        content: str,
        attachments: list[object],
        consumer: TelegramStreamConsumer,
    ) -> AgentRunRead:
        run: AgentRunRead | None = None
        try:
            async for event in self.bill_helper_api.stream_thread_message(
                thread_id=thread_id,
                content=content,
                files=attachments,
            ):
                await consumer.consume_event(event)
                if consumer.run_id is not None and run is None:
                    self.state_store.set_active_run(chat_id, consumer.run_id)
            if consumer.run_id is None:
                raise BillHelperApiStreamError("Bill Helper stream ended before returning a run id.")
            run = await asyncio.to_thread(self.bill_helper_api.get_run, consumer.run_id)
        except BillHelperApiStreamError:
            if consumer.run_id is None:
                run = await asyncio.to_thread(
                    self.bill_helper_api.send_thread_message,
                    thread_id=thread_id,
                    content=content,
                    files=attachments,
                )
            else:
                run = await asyncio.to_thread(self.bill_helper_api.get_run, consumer.run_id)

        self.state_store.set_active_run(chat_id, run.id)
        if run.status.value == "running":
            return await self.poll_run_until_terminal(run.id, seed_run=run)
        return run

    async def _resolve_target_thread(self, chat_id: int, message_thread_id: int | None) -> str:
        state = self.state_store.get(chat_id)
        topics_enabled = bool(state.topics_enabled) if state is not None else False
        if topics_enabled and message_thread_id is not None:
            mapped_thread = self.state_store.get_thread_for_topic(chat_id, message_thread_id)
            if mapped_thread:
                self.state_store.set_active_thread(chat_id, mapped_thread)
                return mapped_thread
            created = await asyncio.to_thread(self.bill_helper_api.create_thread)
            self.state_store.bind_topic_thread(chat_id, message_thread_id=message_thread_id, thread_id=created.id)
            self.state_store.set_active_thread(chat_id, created.id)
            return created.id
        return await self._ensure_active_thread(chat_id)

    async def _sync_topic_name(self, *, chat_id: int, thread_id: str, bot: object) -> None:
        topic_id = self.state_store.get_topic_for_thread(chat_id, thread_id)
        if topic_id is None:
            return
        detail = await asyncio.to_thread(self.bill_helper_api.get_thread, thread_id)
        title = (detail.thread.title or "").strip()
        if not title:
            return
        try:
            await bot.edit_forum_topic(chat_id=chat_id, message_thread_id=topic_id, name=title)
        except BadRequest as exc:
            lowered = str(exc).lower()
            if "not modified" in lowered or "topic not modified" in lowered:
                return
            raise
