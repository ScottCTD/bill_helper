from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.enums import AgentMessageRole
from backend.models import AgentMessage
from backend.services.agent.prompts import system_prompt


def attachment_to_data_url(file_path: str, mime_type: str) -> str | None:
    path = Path(file_path)
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_user_content(message: AgentMessage) -> str | list[dict[str, Any]]:
    if not message.attachments:
        return message.content_markdown

    parts: list[dict[str, Any]] = []
    if message.content_markdown.strip():
        parts.append({"type": "text", "text": message.content_markdown})
    for attachment in message.attachments:
        data_url = attachment_to_data_url(attachment.file_path, attachment.mime_type)
        if data_url is None:
            continue
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    if not parts:
        return message.content_markdown or "User sent image attachments."
    return parts


def build_llm_messages(db: Session, thread_id: str) -> list[dict[str, Any]]:
    history = list(
        db.scalars(
            select(AgentMessage)
            .where(AgentMessage.thread_id == thread_id)
            .options(selectinload(AgentMessage.attachments))
            .order_by(AgentMessage.created_at.asc())
        )
    )
    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt()}]
    for message in history:
        if message.role == AgentMessageRole.USER:
            messages.append({"role": "user", "content": build_user_content(message)})
            continue
        if message.role == AgentMessageRole.ASSISTANT:
            messages.append({"role": "assistant", "content": message.content_markdown})
            continue
        messages.append({"role": "system", "content": message.content_markdown})
    return messages
