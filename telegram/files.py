from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from mimetypes import guess_type
from pathlib import Path
import shutil
import tempfile

from telegram.bill_helper_api import AttachmentUpload
from telegram.ptb import File as TelegramFile
from telegram.ptb import Message as TelegramMessage

DEFAULT_PHOTO_FILENAME = "telegram-photo.jpg"
PDF_MIME_TYPE = "application/pdf"


class TelegramAttachmentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class DownloadedTelegramAttachment:
    filename: str
    mime_type: str
    path: Path
    size_bytes: int

    def to_upload(self) -> AttachmentUpload:
        return AttachmentUpload(
            filename=self.filename,
            mime_type=self.mime_type,
            content=self.path.read_bytes(),
        )


@dataclass(frozen=True, slots=True)
class _AttachmentRef:
    file_id: str
    filename_hint: str | None
    mime_type_hint: str | None
    size_hint: int | None
    is_photo: bool = False


def extract_attachment_ref(message: TelegramMessage) -> _AttachmentRef | None:
    if message.photo:
        largest = max(message.photo, key=lambda item: (item.file_size or 0, item.width or 0, item.height or 0))
        return _AttachmentRef(
            file_id=largest.file_id,
            filename_hint=DEFAULT_PHOTO_FILENAME,
            mime_type_hint="image/jpeg",
            size_hint=largest.file_size,
            is_photo=True,
        )
    if message.document is not None:
        return _AttachmentRef(
            file_id=message.document.file_id,
            filename_hint=message.document.file_name,
            mime_type_hint=_normalize_mime_type(message.document.mime_type),
            size_hint=message.document.file_size,
        )
    return None


@asynccontextmanager
async def download_message_attachments(
    *,
    message: TelegramMessage,
    max_size_bytes: int,
    max_attachments: int,
) -> AsyncIterator[list[DownloadedTelegramAttachment]]:
    attachment_ref = extract_attachment_ref(message)
    if attachment_ref is None:
        yield []
        return
    if max_attachments < 1:
        raise TelegramAttachmentError("Attachments are currently unavailable for this bot.")

    temp_dir = Path(tempfile.mkdtemp(prefix="bill-helper-telegram-"))
    try:
        attachment = await _download_attachment(
            attachment_ref=attachment_ref,
            message=message,
            temp_dir=temp_dir,
            max_size_bytes=max_size_bytes,
        )
        yield [attachment]
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


async def _download_attachment(
    *,
    attachment_ref: _AttachmentRef,
    message: TelegramMessage,
    temp_dir: Path,
    max_size_bytes: int,
) -> DownloadedTelegramAttachment:
    telegram_file = await message.get_bot().get_file(attachment_ref.file_id)
    if telegram_file.file_path is None:
        raise TelegramAttachmentError("Telegram did not return a downloadable file path.")

    advertised_size = telegram_file.file_size or attachment_ref.size_hint or 0
    if advertised_size > max_size_bytes:
        raise TelegramAttachmentError(f"Attachment too large. Max bytes allowed is {max_size_bytes}.")

    mime_type = _resolve_mime_type(attachment_ref, telegram_file)
    if not _is_supported_mime_type(mime_type):
        raise TelegramAttachmentError("Only image and PDF attachments are supported.")

    filename = _resolve_filename(attachment_ref, telegram_file, mime_type)
    temp_path = temp_dir / filename
    await telegram_file.download_to_drive(custom_path=temp_path)
    file_size = temp_path.stat().st_size
    if file_size > max_size_bytes:
        raise TelegramAttachmentError(f"Attachment too large. Max bytes allowed is {max_size_bytes}.")

    return DownloadedTelegramAttachment(
        filename=filename,
        mime_type=mime_type,
        path=temp_path,
        size_bytes=file_size,
    )


def _resolve_mime_type(attachment_ref: _AttachmentRef, telegram_file: TelegramFile) -> str:
    mime_type = attachment_ref.mime_type_hint
    if mime_type is None and telegram_file.file_path:
        mime_type = _normalize_mime_type(guess_type(telegram_file.file_path)[0])
    if mime_type is not None:
        return mime_type
    return "image/jpeg" if attachment_ref.is_photo else "application/octet-stream"


def _resolve_filename(attachment_ref: _AttachmentRef, telegram_file: TelegramFile, mime_type: str) -> str:
    for candidate in (attachment_ref.filename_hint, telegram_file.file_path):
        normalized = Path(candidate or "").name
        if normalized:
            return normalized
    if mime_type == PDF_MIME_TYPE:
        return "attachment.pdf"
    return DEFAULT_PHOTO_FILENAME if attachment_ref.is_photo else "attachment.bin"


def _normalize_mime_type(value: str | None) -> str | None:
    normalized = (value or "").strip().lower()
    return normalized or None


def _is_supported_mime_type(mime_type: str) -> bool:
    return mime_type == PDF_MIME_TYPE or mime_type.startswith("image/")