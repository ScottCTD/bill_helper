from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from backend.schemas_agent import AgentMessageRead, AgentRunRead
from telegram.bill_helper_api import BillHelperApiClient, BillHelperApiError
from telegram.files import TelegramAttachmentError, download_message_attachments
from telegram.formatting import format_status_html, render_telegram_reply_chunks, simplify_markdown_for_telegram
from telegram.ptb import Message as TelegramMessage
from telegram.state import ChatStateStore


@dataclass(slots=True)
class TelegramContentHandler:
    bill_helper_api: BillHelperApiClient
    state_store: ChatStateStore
    poll_interval_seconds: float = 1.0
    max_polls: int = 120
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    telegram_api: object | None = None

    async def handle_message(self, message: TelegramMessage) -> list[TelegramMessage]:
        chat_id = message.chat_id

        try:
            thread_id = await self._ensure_active_thread(chat_id)
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
                run = await asyncio.to_thread(
                    self.bill_helper_api.send_thread_message,
                    thread_id=thread_id,
                    content=content,
                    files=[attachment.to_upload() for attachment in attachments],
                )
        except TelegramAttachmentError as exc:
            return [
                await message.reply_html(format_status_html("Attachment rejected", str(exc)))
            ]
        except BillHelperApiError as exc:
            return [
                await message.reply_html(format_status_html("Bill Helper request failed", str(exc)))
            ]

        self.state_store.set_active_run(chat_id, run.id)
        sent_messages: list[TelegramMessage] = []
        try:
            terminal_run = run
            if run.status.value == "running":
                sent_messages.append(
                    await message.reply_html(
                        format_status_html(
                            "Working on it…",
                            "I’ll send the final reply here as soon as it finishes.",
                        )
                    )
                )
                terminal_run = await self.poll_run_until_terminal(run.id, seed_run=run)
            sent_messages.extend(await self._deliver_terminal_reply(message=message, run=terminal_run))
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

    async def _deliver_terminal_reply(self, *, message: TelegramMessage, run: AgentRunRead) -> list[TelegramMessage]:
        if run.status.value != "completed":
            error_text = (run.error_text or "The request did not complete.").strip()
            return [
                await message.reply_html(format_status_html("Request failed", error_text))
            ]

        final_reply = await self._resolve_final_reply(run)
        chunks = render_telegram_reply_chunks(final_reply or "The run completed, but no final reply was returned.")
        sent_messages: list[TelegramMessage] = []
        for chunk in chunks:
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