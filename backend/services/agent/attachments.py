from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

from backend.models_agent import AgentThread


def thread_attachment_directories(
    thread: AgentThread,
    *,
    upload_root: Path,
) -> set[Path]:
    resolved_upload_root = upload_root.resolve()
    directories: set[Path] = set()
    for message in thread.messages:
        for attachment in message.attachments:
            directory = Path(attachment.file_path).parent
            resolved_directory = directory.resolve()
            if resolved_directory == resolved_upload_root:
                continue
            if resolved_upload_root in resolved_directory.parents:
                directories.add(resolved_directory)
    return directories


def delete_attachment_directories(directories: set[Path]) -> None:
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        shutil.rmtree(directory, ignore_errors=True)


def store_attachment_bytes(
    *,
    upload_root: Path,
    message_id: str,
    mime_type: str,
    original_filename: str | None,
    file_bytes: bytes,
) -> str:
    message_upload_root = upload_root / message_id
    message_upload_root.mkdir(parents=True, exist_ok=True)
    suffix = Path(original_filename or "").suffix
    if not suffix:
        if mime_type == "image/png":
            suffix = ".png"
        elif mime_type == "image/jpeg":
            suffix = ".jpg"
        elif mime_type == "image/webp":
            suffix = ".webp"
        elif mime_type == "application/pdf":
            suffix = ".pdf"
        else:
            suffix = ".bin"
    file_path = message_upload_root / f"{uuid4()}{suffix}"
    _atomic_write_bytes(file_path, file_bytes)
    return str(file_path)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.tmp-",
        dir=str(path.parent),
    )
    temp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
