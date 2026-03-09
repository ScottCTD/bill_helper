from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from backend.schemas_agent import AgentRunRead, AgentThreadDetailRead, AgentThreadRead, AgentThreadSummaryRead
from backend.schemas_finance import RuntimeSettingsOverridesRead, RuntimeSettingsRead
from telegram.commands import (
    INVALID_THREAD_SELECTOR_REPLY,
    TelegramBotHandlers,
    TelegramCommandRouter,
    UNAUTHORIZED_PRIVATE_REPLY,
    register_application_handlers,
)
from telegram.ptb import CommandHandler, MessageHandler
from telegram.state import ChatStateStore


THREAD_1_ID = "11111111-1111-1111-1111-111111111111"
THREAD_2_ID = "22222222-2222-2222-2222-222222222222"


class FakeBillHelperApiClient:
    def __init__(self) -> None:
        self.settings = RuntimeSettingsRead(
            current_user_name="admin",
            user_memory=None,
            default_currency_code="CAD",
            dashboard_currency_code="CAD",
            agent_model="openrouter/qwen/qwen3.5-27b",
            available_agent_models=[
                "openrouter/qwen/qwen3.5-27b",
                "openai/gpt-4.1-mini",
            ],
            agent_max_steps=100,
            agent_bulk_max_concurrent_threads=4,
            agent_retry_max_attempts=3,
            agent_retry_initial_wait_seconds=0.25,
            agent_retry_max_wait_seconds=4.0,
            agent_retry_backoff_multiplier=2.0,
            agent_max_image_size_bytes=5242880,
            agent_max_images_per_message=4,
            agent_base_url=None,
            agent_api_key_configured=False,
            overrides=RuntimeSettingsOverridesRead(agent_api_key_configured=False),
        )
        self.threads = [
            AgentThreadSummaryRead.model_validate(
                {
                    "id": THREAD_1_ID,
                    "title": "Receipts",
                    "created_at": "2026-03-08T00:00:00Z",
                    "updated_at": "2026-03-08T00:00:00Z",
                    "last_message_preview": "Latest",
                    "pending_change_count": 0,
                    "has_running_run": False,
                }
            ),
            AgentThreadSummaryRead.model_validate(
                {
                    "id": THREAD_2_ID,
                    "title": "Taxes",
                    "created_at": "2026-03-08T00:00:00Z",
                    "updated_at": "2026-03-08T00:00:00Z",
                    "last_message_preview": None,
                    "pending_change_count": 0,
                    "has_running_run": True,
                }
            ),
        ]
        self.patched_models: list[str] = []
        self.interrupted_runs: list[str] = []
        self.create_thread_calls = 0
        self.list_threads_calls = 0
        self.get_thread_calls: list[str] = []
        self.runs: dict[str, AgentRunRead] = {
            "run-1": AgentRunRead.model_validate(
                {
                    "id": "run-1",
                    "thread_id": THREAD_2_ID,
                    "user_message_id": "msg-1",
                    "assistant_message_id": None,
                    "status": "running",
                    "model_name": self.settings.agent_model,
                    "surface": "telegram",
                    "context_tokens": 8,
                    "input_tokens": None,
                    "output_tokens": None,
                    "cache_read_tokens": None,
                    "cache_write_tokens": None,
                    "input_cost_usd": None,
                    "output_cost_usd": None,
                    "total_cost_usd": None,
                    "error_text": None,
                    "created_at": "2026-03-08T00:00:00Z",
                    "completed_at": None,
                    "events": [],
                    "tool_calls": [],
                    "change_items": [],
                }
            )
        }

    def list_threads(self) -> list[AgentThreadSummaryRead]:
        self.list_threads_calls += 1
        return list(self.threads)

    def create_thread(self, *, title: str | None = None) -> AgentThreadRead:
        self.create_thread_calls += 1
        thread = AgentThreadRead.model_validate(
            {
                "id": f"thread-{len(self.threads) + 1}",
                "title": title,
                "created_at": "2026-03-08T00:00:00Z",
                "updated_at": "2026-03-08T00:00:00Z",
            }
        )
        self.threads.insert(
            0,
            AgentThreadSummaryRead.model_validate(
                {
                    **thread.model_dump(mode="json"),
                    "last_message_preview": None,
                    "pending_change_count": 0,
                    "has_running_run": False,
                }
            ),
        )
        return thread

    def get_thread(self, thread_id: str) -> AgentThreadDetailRead:
        self.get_thread_calls.append(thread_id)
        thread = next(thread for thread in self.threads if thread.id == thread_id)
        runs = [run.model_dump(mode="json") for run in self.runs.values() if run.thread_id == thread_id]
        return AgentThreadDetailRead.model_validate(
            {
                "thread": {
                    "id": thread.id,
                    "title": thread.title,
                    "created_at": thread.created_at,
                    "updated_at": thread.updated_at,
                },
                "messages": [],
                "runs": runs,
                "configured_model_name": self.settings.agent_model,
                "current_context_tokens": 32,
            }
        )

    def get_settings(self) -> RuntimeSettingsRead:
        return self.settings

    def patch_settings(self, payload: dict[str, str]) -> RuntimeSettingsRead:
        self.settings = self.settings.model_copy(update={"agent_model": payload["agent_model"]})
        self.patched_models.append(payload["agent_model"])
        return self.settings

    def get_run(self, run_id: str) -> AgentRunRead:
        return self.runs[run_id]

    def interrupt_run(self, run_id: str) -> AgentRunRead:
        self.interrupted_runs.append(run_id)
        interrupted = AgentRunRead.model_validate(
            {
                **self.runs[run_id].model_dump(mode="json"),
                "status": "failed",
                "error_text": "Run interrupted by user.",
                "completed_at": "2026-03-08T00:00:05Z",
            }
        )
        self.runs[run_id] = interrupted
        return interrupted


class ReplyRecorder:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class PtbDocumentStub:
    def __init__(self) -> None:
        self.file_id = "doc-1"
        self.file_unique_id = "uniq-1"
        self.file_name = "receipt.pdf"
        self.mime_type = "application/pdf"
        self.file_size = 9


class PtbMessageStub(ReplyRecorder):
    def __init__(
        self,
        *,
        text: str | None = None,
        caption: str | None = None,
        chat_type: str = "private",
        user_id: int = 12345,
    ) -> None:
        super().__init__()
        self.message_id = 99
        self.text = text
        self.caption = caption
        self.chat = SimpleNamespace(id=12345, type=chat_type)
        self.from_user = SimpleNamespace(id=user_id)
        self.date = None
        self.photo = []
        self.document = PtbDocumentStub() if caption is not None else None


def _ptb_update(
    *,
    text: str | None = None,
    caption: str | None = None,
    chat_type: str = "private",
    user_id: int = 12345,
):
    message = PtbMessageStub(text=text, caption=caption, chat_type=chat_type, user_id=user_id)
    return SimpleNamespace(
        effective_message=message,
        effective_chat=message.chat,
        effective_user=message.from_user,
    ), message


def test_threads_and_use_switch_active_thread(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    router = TelegramCommandRouter(api_client=api_client, state_store=state_store)

    listed = router.handle_threads(12345)
    switched = router.handle_use(12345, "2")

    assert "Recent threads:" in listed
    assert f"2. Taxes [running] — {THREAD_2_ID}" in listed
    assert switched == f"Switched to thread: Taxes ({THREAD_2_ID})"
    assert state_store.get(12345).active_thread_id == THREAD_2_ID


def test_use_accepts_thread_uuid_selector(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    router = TelegramCommandRouter(api_client=api_client, state_store=state_store)

    switched = router.handle_use(12345, THREAD_2_ID.upper())

    assert switched == f"Switched to thread: Taxes ({THREAD_2_ID})"
    assert api_client.get_thread_calls == [THREAD_2_ID]


def test_use_rejects_invalid_thread_selector_before_backend_lookup(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    router = TelegramCommandRouter(api_client=api_client, state_store=state_store)

    reply = router.handle_use(12345, "../settings")

    assert reply == INVALID_THREAD_SELECTOR_REPLY
    assert api_client.get_thread_calls == []
    assert state_store.get(12345) is None


def test_model_stop_and_status_update_state(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    state_store.set_active_thread(12345, THREAD_2_ID)
    state_store.set_active_run(12345, "run-1")
    router = TelegramCommandRouter(api_client=api_client, state_store=state_store)

    model_reply = router.handle_model("openai/gpt-4.1")
    stop_reply = router.handle_stop(12345)
    status_reply = router.handle_status(12345)

    assert model_reply == "Updated model to openai/gpt-4.1."
    assert stop_reply == "Stopped run run-1: Run interrupted by user."
    assert status_reply == f"Model: openai/gpt-4.1\nActive thread: Taxes ({THREAD_2_ID})\nRun: idle"
    assert api_client.patched_models == ["openai/gpt-4.1"]
    assert api_client.interrupted_runs == ["run-1"]
    assert state_store.get(12345).active_run_id is None


def test_ptb_command_handler_replies_with_router_text(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    handlers = TelegramBotHandlers(
        command_router=TelegramCommandRouter(api_client=api_client, state_store=state_store),
        allowed_user_ids=frozenset({12345}),
    )
    update, message = _ptb_update(text="/help")

    asyncio.run(handlers.handle_help(update, SimpleNamespace(args=[])))

    assert message.replies and message.replies[0].startswith("Commands:")


def test_ptb_command_handler_rejects_unauthorized_private_user(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    handlers = TelegramBotHandlers(
        command_router=TelegramCommandRouter(api_client=api_client, state_store=state_store)
    )
    update, message = _ptb_update(text="/new", user_id=99999)

    asyncio.run(handlers.handle_new(update, SimpleNamespace(args=[])))

    assert message.replies == [UNAUTHORIZED_PRIVATE_REPLY]
    assert api_client.create_thread_calls == 0
    assert state_store.get(12345) is None


def test_ptb_message_handler_converts_and_forwards_private_messages(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    forwarded: list[object] = []

    async def record_message(message) -> None:
        forwarded.append(message)

    handlers = TelegramBotHandlers(
        command_router=TelegramCommandRouter(api_client=api_client, state_store=state_store),
        message_handler=record_message,
        allowed_user_ids=frozenset({12345}),
    )
    update, message = _ptb_update(caption="Please review")

    asyncio.run(handlers.handle_content_message(update, SimpleNamespace()))

    assert forwarded == [message]


def test_ptb_message_handler_rejects_unauthorized_private_user(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    forwarded: list[object] = []

    async def record_message(message) -> None:
        forwarded.append(message)

    handlers = TelegramBotHandlers(
        command_router=TelegramCommandRouter(api_client=api_client, state_store=state_store),
        message_handler=record_message,
    )
    update, message = _ptb_update(text="hello", user_id=99999)

    asyncio.run(handlers.handle_content_message(update, SimpleNamespace()))

    assert forwarded == []
    assert message.replies == [UNAUTHORIZED_PRIVATE_REPLY]


def test_ptb_message_handler_ignores_non_private_chat(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    forwarded: list[object] = []

    async def record_message(message) -> None:
        forwarded.append(message)

    handlers = TelegramBotHandlers(
        command_router=TelegramCommandRouter(api_client=api_client, state_store=state_store),
        message_handler=record_message,
    )
    update, _message = _ptb_update(text="hello", chat_type="group")

    asyncio.run(handlers.handle_content_message(update, SimpleNamespace()))

    assert forwarded == []


def test_register_application_handlers_adds_ptb_command_and_message_handlers(tmp_path):
    api_client = FakeBillHelperApiClient()
    state_store = ChatStateStore(Path(tmp_path) / "chat_state.json")
    handlers = TelegramBotHandlers(
        command_router=TelegramCommandRouter(api_client=api_client, state_store=state_store)
    )

    class FakeApplication:
        def __init__(self) -> None:
            self.handlers: list[object] = []

        def add_handler(self, handler: object) -> None:
            self.handlers.append(handler)

    application = FakeApplication()
    register_application_handlers(application, handlers)

    assert len(application.handlers) == 10
    assert sum(isinstance(handler, CommandHandler) for handler in application.handlers) == 9
    assert isinstance(application.handlers[-1], MessageHandler)
