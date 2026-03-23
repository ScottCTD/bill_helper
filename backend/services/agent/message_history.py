# CALLING SPEC:
# - Purpose: implement focused service logic for `message_history`.
# - Inputs: callers that import `backend/services/agent/message_history.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `message_history`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.config import get_settings
from backend.enums_agent import AgentMessageRole
from backend.models_agent import AgentMessage, AgentMessageAttachment
from backend.services.agent.message_history_content import (
    build_entity_category_context as _build_entity_category_context,
)
from backend.services.agent.message_history_content import build_user_content
from backend.services.agent.message_history_prefixes import (
    build_interruption_prefix_for_current_turn as _build_interruption_prefix_for_current_turn,
)
from backend.services.agent.message_history_prefixes import (
    build_review_results_prefix_for_current_turn as _build_review_results_prefix_for_current_turn,
)
from backend.services.agent.principal_scope import load_thread_owner_user
from backend.services.agent.prompts import SystemPromptContext, system_prompt
from backend.services.agent.user_context import (
    build_current_user_context as _build_current_user_context,
)
from backend.services.runtime_settings import resolve_runtime_settings


def build_llm_messages(
    db: Session,
    thread_id: str,
    *,
    current_user_message_id: str | None = None,
    model_name: str | None = None,
    surface: str = "app",
) -> list[dict[str, Any]]:
    settings = resolve_runtime_settings(db)
    owner_user = load_thread_owner_user(db, thread_id=thread_id)

    history = list(
        db.scalars(
            select(AgentMessage)
            .where(AgentMessage.thread_id == thread_id)
            .options(
                selectinload(AgentMessage.attachments).selectinload(
                    AgentMessageAttachment.user_file
                )
            )
            .order_by(AgentMessage.created_at.asc())
        )
    )
    review_results_prefix = _build_review_results_prefix_for_current_turn(
        db,
        thread_id=thread_id,
        history=history,
        current_user_message_id=current_user_message_id,
    )
    interruption_prefix = _build_interruption_prefix_for_current_turn(
        db,
        thread_id=thread_id,
        history=history,
        current_user_message_id=current_user_message_id,
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": system_prompt(
                SystemPromptContext(
                    current_user_context=_build_current_user_context(
                        db,
                        user_id=owner_user.id if owner_user is not None else None,
                        user_name=owner_user.name if owner_user is not None else None,
                    ),
                    entity_category_context=_build_entity_category_context(
                        db,
                        owner_user_id=owner_user.id if owner_user is not None else None,
                    ),
                    user_memory=settings.user_memory,
                    current_timezone=get_settings().current_user_timezone,
                    response_surface=surface,
                )
            ),
        }
    ]
    for message in history:
        if message.role == AgentMessageRole.USER:
            message_review_prefix = (
                review_results_prefix if message.id == current_user_message_id else None
            )
            message_interruption_prefix = (
                interruption_prefix if message.id == current_user_message_id else None
            )
            messages.append(
                {
                    "role": "user",
                    "content": build_user_content(
                        message,
                        review_results_prefix=message_review_prefix,
                        interruption_prefix=message_interruption_prefix,
                    ),
                }
            )
            continue
        if message.role == AgentMessageRole.ASSISTANT:
            messages.append({"role": "assistant", "content": message.content_markdown})
            continue
        messages.append({"role": "system", "content": message.content_markdown})
    return messages
