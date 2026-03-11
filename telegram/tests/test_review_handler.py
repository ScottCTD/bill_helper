from __future__ import annotations

import asyncio
from types import SimpleNamespace

from backend.schemas_agent import AgentRunRead
from telegram.review_handler import TelegramReviewHandler
from telegram.state import ChatStateStore


def _run_with_change_items(*statuses: str) -> AgentRunRead:
    return AgentRunRead.model_validate(
        {
            "id": "run-1",
            "thread_id": "thread-1",
            "user_message_id": "msg-1",
            "assistant_message_id": "msg-2",
            "terminal_assistant_reply": "Done.",
            "status": "completed",
            "model_name": "openai/gpt-4.1",
            "surface": "telegram",
            "reply_surface": "telegram",
            "created_at": "2026-03-08T00:00:00Z",
            "completed_at": "2026-03-08T00:00:05Z",
            "events": [],
            "tool_calls": [],
            "change_items": [
                {
                    "id": f"item-{index}",
                    "run_id": "run-1",
                    "change_type": "create_entry",
                    "payload_json": {
                        "name": f"Entry {index}",
                        "amount_minor": 1000 * index,
                        "currency_code": "CAD",
                    },
                    "rationale_text": "Looks correct.",
                    "status": status,
                    "review_note": None,
                    "applied_resource_type": None,
                    "applied_resource_id": None,
                    "created_at": "2026-03-08T00:00:00Z",
                    "updated_at": "2026-03-08T00:00:05Z",
                    "review_actions": [],
                }
                for index, status in enumerate(statuses, start=1)
            ],
        }
    )


class FakeBot:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, object]] = []
        self.edited_messages: list[dict[str, object]] = []

    async def send_message(self, **kwargs):
        self.sent_messages.append(kwargs)
        return SimpleNamespace(message_id=len(self.sent_messages), **kwargs)

    async def edit_message_text(self, **kwargs):
        self.edited_messages.append(kwargs)


def test_render_change_items_sends_one_message_per_item_and_summary(tmp_path):
    handler = TelegramReviewHandler(
        api_client=SimpleNamespace(),
        state_store=ChatStateStore(tmp_path / "chat_state.json"),
    )
    bot = FakeBot()

    sent = asyncio.run(
        handler.render_change_items(
            bot=bot,
            chat_id=123,
            run=_run_with_change_items("PENDING_REVIEW", "PENDING_REVIEW"),
            message_thread_id=77,
        )
    )

    assert len(sent) == 3
    assert bot.sent_messages[0]["message_thread_id"] == 77
    assert bot.sent_messages[1]["message_thread_id"] == 77
    assert "changes proposed" in bot.sent_messages[2]["text"]
    review_run = handler.state_store.get_review_run(123, "run-1")
    assert review_run is not None
    assert review_run.item_message_ids == {"item-1": 1, "item-2": 2}
    assert review_run.summary_message_id == 3


def test_render_change_item_includes_tags_for_create_entry(tmp_path):
    handler = TelegramReviewHandler(
        api_client=SimpleNamespace(),
        state_store=ChatStateStore(tmp_path / "chat_state.json"),
    )
    bot = FakeBot()
    run = AgentRunRead.model_validate(
        {
            "id": "run-2",
            "thread_id": "thread-1",
            "user_message_id": "msg-1",
            "assistant_message_id": "msg-2",
            "terminal_assistant_reply": "Done.",
            "status": "completed",
            "model_name": "openai/gpt-4.1",
            "surface": "telegram",
            "reply_surface": "telegram",
            "created_at": "2026-03-08T00:00:00Z",
            "completed_at": "2026-03-08T00:00:05Z",
            "events": [],
            "tool_calls": [],
            "change_items": [
                {
                    "id": "item-1",
                    "run_id": "run-2",
                    "change_type": "create_entry",
                    "payload_json": {
                        "name": "Groceries",
                        "amount_minor": 1234,
                        "currency_code": "CAD",
                        "tags": ["food", "household"],
                    },
                    "rationale_text": "Receipt matches.",
                    "status": "PENDING_REVIEW",
                    "review_note": None,
                    "applied_resource_type": None,
                    "applied_resource_id": None,
                    "created_at": "2026-03-08T00:00:00Z",
                    "updated_at": "2026-03-08T00:00:05Z",
                    "review_actions": [],
                }
            ],
        }
    )

    asyncio.run(handler.render_change_items(bot=bot, chat_id=123, run=run))

    assert "Tags: <b>food, household</b>" in bot.sent_messages[0]["text"]


def test_handle_batch_action_updates_items_and_summary(tmp_path):
    class ApiClientStub:
        def __init__(self) -> None:
            self.run = _run_with_change_items("PENDING_REVIEW", "PENDING_REVIEW")

        def get_run(self, run_id: str) -> AgentRunRead:
            assert run_id == "run-1"
            return self.run

        def approve_change_item(self, item_id: str):
            payload = self.run.model_dump(mode="json")
            for item in payload["change_items"]:
                if item["id"] == item_id:
                    item["status"] = "APPLIED"
            self.run = AgentRunRead.model_validate(payload)
            return next(item for item in self.run.change_items if item.id == item_id)

    api_client = ApiClientStub()
    state_store = ChatStateStore(tmp_path / "chat_state.json")
    state_store.bind_review_item_message(123, run_id="run-1", item_id="item-1", message_id=10)
    state_store.bind_review_item_message(123, run_id="run-1", item_id="item-2", message_id=11)
    state_store.bind_review_summary_message(123, run_id="run-1", message_id=12)
    handler = TelegramReviewHandler(api_client=api_client, state_store=state_store)
    bot = FakeBot()

    asyncio.run(
        handler.handle_callback(
            SimpleNamespace(
                callback_query=SimpleNamespace(
                    data="ci:approve_all:run-1",
                    message=SimpleNamespace(chat=SimpleNamespace(id=123)),
                    answer=lambda *args, **kwargs: asyncio.sleep(0),
                    get_bot=lambda: bot,
                )
            ),
            SimpleNamespace(),
        )
    )

    assert len(bot.edited_messages) == 3
    assert bot.edited_messages[-1]["message_id"] == 12
    assert "Review complete" in bot.edited_messages[-1]["text"]
