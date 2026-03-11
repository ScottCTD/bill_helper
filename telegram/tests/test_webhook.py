from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from telegram.config import TelegramSettings
from telegram.webhook import TELEGRAM_WEBHOOK_HEADER_NAME, WEBHOOK_PATH, create_app


class FakeApplication:
    def __init__(self) -> None:
        self.bot = SimpleBot()
        self.lifecycle: list[str] = []
        self.processed_updates: list[object] = []

    async def initialize(self) -> None:
        self.lifecycle.append("initialize")

    async def start(self) -> None:
        self.lifecycle.append("start")

    async def stop(self) -> None:
        self.lifecycle.append("stop")

    async def shutdown(self) -> None:
        self.lifecycle.append("shutdown")

    async def process_update(self, update) -> None:
        self.processed_updates.append(update)


class SimpleBot:
    def __init__(self) -> None:
        self.commands = []

    async def set_my_commands(self, commands) -> None:
        self.commands = list(commands)


def test_webhook_validates_secret_and_dispatches_update(tmp_path):
    application = FakeApplication()
    settings = TelegramSettings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="bot-token",
        TELEGRAM_WEBHOOK_SECRET="secret-token",
        TELEGRAM_DATA_DIR=str(tmp_path),
    )
    app = create_app(settings, application=application, update_loader=lambda payload, bot: {"payload": payload, "bot": bot})

    with TestClient(app) as client:
        response = client.post(
            WEBHOOK_PATH,
            headers={TELEGRAM_WEBHOOK_HEADER_NAME: "secret-token"},
            json={
                "update_id": 55,
                "message": {"message_id": 3, "chat": {"id": 7, "type": "private"}, "text": "/help"},
            },
        )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert application.processed_updates == [
        {
            "payload": {
                "update_id": 55,
                "message": {"message_id": 3, "chat": {"id": 7, "type": "private"}, "text": "/help"},
            },
            "bot": application.bot,
        }
    ]
    assert application.lifecycle == ["initialize", "start", "stop", "shutdown"]


def test_webhook_rejects_missing_or_invalid_secret(tmp_path):
    application = FakeApplication()
    settings = TelegramSettings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="bot-token",
        TELEGRAM_WEBHOOK_SECRET="secret-token",
        TELEGRAM_DATA_DIR=str(tmp_path),
    )
    app = create_app(settings, application=application, update_loader=lambda payload, bot: {"payload": payload, "bot": bot})
    payload = {
        "update_id": 55,
        "message": {"message_id": 3, "chat": {"id": 7, "type": "private"}, "text": "/help"},
    }

    with TestClient(app) as client:
        missing = client.post(WEBHOOK_PATH, json=payload)
        invalid = client.post(WEBHOOK_PATH, headers={TELEGRAM_WEBHOOK_HEADER_NAME: "wrong"}, json=payload)

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert application.processed_updates == []


def test_webhook_requires_configured_secret(tmp_path):
    settings = TelegramSettings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="bot-token",
        TELEGRAM_DATA_DIR=str(tmp_path),
    )

    with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_SECRET"):
        create_app(settings)
