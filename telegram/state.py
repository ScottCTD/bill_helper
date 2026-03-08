from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from tempfile import mkstemp
from threading import RLock

from pydantic import BaseModel, Field

from telegram.config import TelegramSettings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ChatStateRecord(BaseModel):
    active_thread_id: str | None = None
    active_run_id: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class _ChatStateFile(BaseModel):
    chats: dict[str, ChatStateRecord] = Field(default_factory=dict)


class ChatStateStore:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = RLock()

    @classmethod
    def from_settings(cls, settings: TelegramSettings) -> ChatStateStore:
        settings.ensure_data_dir()
        return cls(settings.state_path or settings.data_dir / "chat_state.json")

    def get(self, chat_id: int) -> ChatStateRecord | None:
        with self._lock:
            state = self._load().chats.get(self._chat_key(chat_id))
            return state.model_copy(deep=True) if state is not None else None

    def set_active_thread(self, chat_id: int, thread_id: str) -> ChatStateRecord:
        with self._lock:
            payload = self._load()
            key = self._chat_key(chat_id)
            state = payload.chats.get(key) or ChatStateRecord()
            if state.active_thread_id != thread_id:
                state.active_thread_id = thread_id
                state.active_run_id = None
            state.updated_at = utc_now()
            payload.chats[key] = state
            self._save(payload)
            return state.model_copy(deep=True)

    def set_active_run(self, chat_id: int, run_id: str) -> ChatStateRecord:
        with self._lock:
            payload = self._load()
            key = self._chat_key(chat_id)
            state = payload.chats.get(key) or ChatStateRecord()
            state.active_run_id = run_id
            state.updated_at = utc_now()
            payload.chats[key] = state
            self._save(payload)
            return state.model_copy(deep=True)

    def clear_active_run(self, chat_id: int) -> ChatStateRecord | None:
        with self._lock:
            payload = self._load()
            key = self._chat_key(chat_id)
            state = payload.chats.get(key)
            if state is None:
                return None
            state.active_run_id = None
            state.updated_at = utc_now()
            payload.chats[key] = state
            self._save(payload)
            return state.model_copy(deep=True)

    def clear_chat(self, chat_id: int) -> None:
        with self._lock:
            payload = self._load()
            if payload.chats.pop(self._chat_key(chat_id), None) is not None:
                self._save(payload)

    def _load(self) -> _ChatStateFile:
        if not self._path.is_file():
            return _ChatStateFile()
        return _ChatStateFile.model_validate_json(self._path.read_text(encoding="utf-8"))

    def _save(self, payload: _ChatStateFile) -> None:
        serialized = json.dumps(payload.model_dump(mode="json"), indent=2) + "\n"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = mkstemp(prefix=f".{self._path.name}.", suffix=".tmp", dir=str(self._path.parent))
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            temp_path.replace(self._path)
        finally:
            temp_path.unlink(missing_ok=True)

    def _chat_key(self, chat_id: int) -> str:
        return str(chat_id)