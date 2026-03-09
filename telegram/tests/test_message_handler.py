from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from backend.schemas_agent import AgentRunRead, AgentThreadDetailRead, AgentThreadRead
from backend.schemas_finance import RuntimeSettingsRead, RuntimeSettingsOverridesRead
from telegram.message_handler import TelegramContentHandler
from telegram.state import ChatStateStore


class FakeTelegramFile:
    def __init__(self, *, file_path: str, file_size: int | None, content: bytes) -> None:
        self.file_path = file_path
        self.file_size = file_size
        self._content = content

    async def download_to_drive(self, custom_path: Path | str | None = None) -> Path:
        target = Path(custom_path or self.file_path)
        target.write_bytes(self._content)
        return target


class FakeTelegramBot:
    def __init__(self, files: dict[str, FakeTelegramFile] | None = None) -> None:
        self.files = files or {}

    async def get_file(self, file_id: str) -> FakeTelegramFile:
        return self.files[file_id]


class FakeTelegramMessage:
    def __init__(
        self,
        *,
        chat_id: int,
        text: str | None = None,
        caption: str | None = None,
        photo=(),
        document=None,
        bot: FakeTelegramBot | None = None,
    ) -> None:
        self.chat_id = chat_id
        self.text = text
        self.caption = caption
        self.photo = tuple(photo)
        self.document = document
        self._bot = bot or FakeTelegramBot()
        self.sent_html: list[str] = []

    def get_bot(self) -> FakeTelegramBot:
        return self._bot

    async def reply_html(self, text: str):
        self.sent_html.append(text)
        return SimpleNamespace(text=text, chat_id=self.chat_id)


def _runtime_settings(*, max_size: int = 1024, max_attachments: int = 4) -> RuntimeSettingsRead:
    return RuntimeSettingsRead(
        current_user_name="admin",
        user_memory=None,
        default_currency_code="CAD",
        dashboard_currency_code="CAD",
        agent_model="openai/gpt-4.1",
        available_agent_models=[
            "openai/gpt-4.1",
            "openai/gpt-4.1-mini",
        ],
        agent_max_steps=100,
        agent_bulk_max_concurrent_threads=4,
        agent_retry_max_attempts=3,
        agent_retry_initial_wait_seconds=0.25,
        agent_retry_max_wait_seconds=4.0,
        agent_retry_backoff_multiplier=2.0,
        agent_max_image_size_bytes=max_size,
        agent_max_images_per_message=max_attachments,
        agent_base_url=None,
        agent_api_key_configured=False,
        overrides=RuntimeSettingsOverridesRead(agent_api_key_configured=False),
    )


def _run(*, status: str, terminal_reply: str | None, assistant_message_id: str | None = None, error_text: str | None = None) -> AgentRunRead:
    return AgentRunRead.model_validate(
        {
            "id": "run-1",
            "thread_id": "thread-1",
            "user_message_id": "msg-1",
            "assistant_message_id": assistant_message_id,
            "terminal_assistant_reply": terminal_reply,
            "status": status,
            "model_name": "openai/gpt-4.1",
            "surface": "telegram",
            "context_tokens": 16,
            "input_tokens": None,
            "output_tokens": None,
            "cache_read_tokens": None,
            "cache_write_tokens": None,
            "input_cost_usd": None,
            "output_cost_usd": None,
            "total_cost_usd": None,
            "error_text": error_text,
            "created_at": "2026-03-08T00:00:00Z",
            "completed_at": None if status == "running" else "2026-03-08T00:00:05Z",
            "events": [],
            "tool_calls": [],
            "change_items": [],
        }
    )


def test_handle_message_forwards_file_polls_run_and_sends_progress_then_reply(tmp_path):
    class BillHelperApiStub:
        def __init__(self) -> None:
            self.sent_messages: list[tuple[str, str, list[tuple[str, str, bytes]]]] = []
            self.run_reads = 0

        def get_settings(self) -> RuntimeSettingsRead:
            return _runtime_settings()

        def create_thread(self, *, title: str | None = None) -> AgentThreadRead:
            return AgentThreadRead.model_validate(
                {"id": "thread-1", "title": title, "created_at": "2026-03-08T00:00:00Z", "updated_at": "2026-03-08T00:00:00Z"}
            )

        def send_thread_message(self, *, thread_id: str, content: str = "", files=()):
            self.sent_messages.append(
                (thread_id, content, [(item.filename, item.mime_type, item.content) for item in files])
            )
            return _run(status="running", terminal_reply=None)

        def get_run(self, run_id: str) -> AgentRunRead:
            self.run_reads += 1
            if self.run_reads == 1:
                return _run(status="running", terminal_reply=None)
            return _run(status="completed", terminal_reply="A & B <done>")

    message = FakeTelegramMessage(
        chat_id=123,
        caption="Please review",
        document=SimpleNamespace(
            file_id="doc-1",
            file_name="receipt.pdf",
            mime_type="application/pdf",
            file_size=9,
        ),
        bot=FakeTelegramBot(
            files={
                "doc-1": FakeTelegramFile(file_path="documents/receipt.pdf", file_size=9, content=b"pdf-bytes")
            }
        ),
    )
    bill_helper_api = BillHelperApiStub()
    handler = TelegramContentHandler(
        bill_helper_api=bill_helper_api,
        state_store=ChatStateStore(tmp_path / "chat_state.json"),
        poll_interval_seconds=0.0,
        sleep=_no_sleep,
    )

    sent = asyncio.run(handler.handle_message(message))

    assert len(sent) == 2
    assert bill_helper_api.sent_messages == [
        ("thread-1", "Please review", [("receipt.pdf", "application/pdf", b"pdf-bytes")])
    ]
    assert message.sent_html[0] == "<b>Working on it…</b>\nI’ll send the final reply here as soon as it finishes."
    assert message.sent_html[1] == "A &amp; B &lt;done&gt;"
    assert handler.state_store.get(123) is not None
    assert handler.state_store.get(123).active_run_id is None


def test_handle_message_falls_back_to_thread_detail_when_run_reply_missing(tmp_path):
    class BillHelperApiStub:
        def get_settings(self) -> RuntimeSettingsRead:
            return _runtime_settings()

        def create_thread(self, *, title: str | None = None) -> AgentThreadRead:
            return AgentThreadRead.model_validate(
                {"id": "thread-1", "title": title, "created_at": "2026-03-08T00:00:00Z", "updated_at": "2026-03-08T00:00:00Z"}
            )

        def send_thread_message(self, *, thread_id: str, content: str = "", files=()):
            return _run(status="completed", terminal_reply=None, assistant_message_id="msg-2")

        def get_thread(self, thread_id: str) -> AgentThreadDetailRead:
            return AgentThreadDetailRead.model_validate(
                {
                    "thread": {"id": thread_id, "title": None, "created_at": "2026-03-08T00:00:00Z", "updated_at": "2026-03-08T00:00:00Z"},
                    "messages": [
                        {
                            "id": "msg-2",
                            "thread_id": thread_id,
                            "role": "assistant",
                            "content_markdown": "## Summary\n**Done**",
                            "created_at": "2026-03-08T00:00:05Z",
                            "attachments": [],
                        }
                    ],
                    "runs": [],
                    "configured_model_name": "openai/gpt-4.1",
                    "current_context_tokens": 16,
                }
            )

    message = FakeTelegramMessage(chat_id=123, text="hello")
    handler = TelegramContentHandler(
        bill_helper_api=BillHelperApiStub(),
        state_store=ChatStateStore(tmp_path / "chat_state.json"),
        poll_interval_seconds=0.0,
        sleep=_no_sleep,
    )

    asyncio.run(handler.handle_message(message))

    assert message.sent_html == ["Summary\nDone"]


def test_handle_message_rejects_empty_unsupported_payload(tmp_path):
    class BillHelperApiStub:
        def get_settings(self) -> RuntimeSettingsRead:
            return _runtime_settings()

        def create_thread(self, *, title: str | None = None) -> AgentThreadRead:
            return AgentThreadRead.model_validate(
                {"id": "thread-1", "title": title, "created_at": "2026-03-08T00:00:00Z", "updated_at": "2026-03-08T00:00:00Z"}
            )

    message = FakeTelegramMessage(chat_id=123)
    handler = TelegramContentHandler(
        bill_helper_api=BillHelperApiStub(),
        state_store=ChatStateStore(tmp_path / "chat_state.json"),
        sleep=_no_sleep,
    )

    asyncio.run(handler.handle_message(message))

    assert message.sent_html == ["<b>Nothing to send</b>\nSend text, a photo, an image document, or a PDF."]


async def _no_sleep(_seconds: float) -> None:
    return None
