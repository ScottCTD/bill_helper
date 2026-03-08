from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from telegram.files import TelegramAttachmentError, download_message_attachments


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
    def __init__(self, files: dict[str, FakeTelegramFile], requests: list[str]) -> None:
        self._files = files
        self._requests = requests

    async def get_file(self, file_id: str) -> FakeTelegramFile:
        self._requests.append(f"get:{file_id}")
        return self._files[file_id]


class FakeTelegramMessage:
    def __init__(self, *, bot: FakeTelegramBot, caption: str | None = None, photo=(), document=None) -> None:
        self.caption = caption
        self.text = None
        self.photo = tuple(photo)
        self.document = document
        self._bot = bot

    def get_bot(self) -> FakeTelegramBot:
        return self._bot


def test_download_message_attachments_builds_upload_from_photo_and_cleans_temp_dir():
    async def scenario() -> tuple[list[str], Path]:
        requests: list[str] = []
        bot = FakeTelegramBot(
            files={
                "large": FakeTelegramFile(file_path="photos/receipt.jpg", file_size=9, content=b"image-bytes"),
            },
            requests=requests,
        )
        message = FakeTelegramMessage(
            bot=bot,
            caption="receipt",
            photo=(
                SimpleNamespace(file_id="small", width=100, height=100, file_size=3),
                SimpleNamespace(file_id="large", width=500, height=500, file_size=9),
            ),
        )

        async with download_message_attachments(
            message=message,
            max_size_bytes=1024,
            max_attachments=1,
        ) as attachments:
            assert len(attachments) == 1
            attachment = attachments[0]
            assert attachment.filename == "telegram-photo.jpg"
            assert attachment.mime_type == "image/jpeg"
            assert attachment.path.is_file()
            assert attachment.to_upload().content == b"image-bytes"
            temp_dir = attachment.path.parent
        return requests, temp_dir

    requests, temp_dir = asyncio.run(scenario())

    assert requests == ["get:large"]
    assert not temp_dir.exists()


def test_download_message_attachments_rejects_unsupported_document_mime_type():
    async def scenario() -> None:
        bot = FakeTelegramBot(
            files={
                "doc-1": FakeTelegramFile(file_path="documents/notes.txt", file_size=5, content=b"notes"),
            },
            requests=[],
        )
        message = FakeTelegramMessage(
            bot=bot,
            document=SimpleNamespace(
                file_id="doc-1",
                file_name="notes.txt",
                mime_type="text/plain",
                file_size=5,
            ),
        )

        with pytest.raises(TelegramAttachmentError, match="Only image and PDF attachments are supported"):
            async with download_message_attachments(
                message=message,
                max_size_bytes=1024,
                max_attachments=1,
            ):
                raise AssertionError("context should not yield")

    asyncio.run(scenario())


def test_download_message_attachments_rejects_oversize_file_before_download():
    async def scenario() -> None:
        bot = FakeTelegramBot(
            files={
                "doc-1": FakeTelegramFile(file_path="documents/receipt.pdf", file_size=2048, content=b"pdf-bytes"),
            },
            requests=[],
        )
        message = FakeTelegramMessage(
            bot=bot,
            document=SimpleNamespace(
                file_id="doc-1",
                file_name="receipt.pdf",
                mime_type="application/pdf",
                file_size=2048,
            ),
        )

        with pytest.raises(TelegramAttachmentError, match="Attachment too large"):
            async with download_message_attachments(
                message=message,
                max_size_bytes=1024,
                max_attachments=1,
            ):
                raise AssertionError("context should not yield")

    asyncio.run(scenario())