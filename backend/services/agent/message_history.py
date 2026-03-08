from __future__ import annotations

from datetime import datetime
from typing import Any

import litellm
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.config import get_settings
from backend.enums_agent import AgentMessageRole, AgentRunStatus
from backend.models_agent import (
    AgentChangeItem,
    AgentMessage,
    AgentReviewAction,
    AgentRun,
    AgentToolCall,
)
from backend.services.agent.attachment_content import (
    AttachmentAssemblyOptions,
    assemble_attachment_parts,
    extract_pdf_text as _extract_pdf_text_impl,
    extract_pdf_text_with_tesseract as _extract_pdf_text_with_tesseract_impl,
    model_supports_vision,
    pdf_page_image_data_urls as _pdf_page_image_data_urls,
)
from backend.services.agent.user_context import (
    build_current_user_context as _build_current_user_context,
)
from backend.services.agent.prompts import SystemPromptContext, system_prompt
from backend.services.agent.proposal_metadata import proposal_metadata_for_change_type
from backend.services.runtime_settings import resolve_runtime_settings
from backend.services.taxonomy import list_term_name_description_pairs


def _model_supports_vision(model_name: str) -> bool:
    return model_supports_vision(
        model_name,
        supports_vision=litellm.supports_vision,
    )


def _extract_pdf_text(file_path: str) -> str | None:
    return _extract_pdf_text_impl(file_path)


def _extract_pdf_text_with_tesseract(file_path: str) -> str | None:
    return _extract_pdf_text_with_tesseract_impl(file_path)


def _normalize_pdf_text_lines(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        normalized_lines.append(" ".join(line.split()))
    return "\n".join(normalized_lines).strip()


def _extract_pdf_text_for_model(file_path: str) -> tuple[str | None, str | None]:
    native_text = _extract_pdf_text(file_path)
    if native_text:
        return native_text, "parsed with PyMuPDF text extraction"
    ocr_text = _extract_pdf_text_with_tesseract(file_path)
    if ocr_text:
        return ocr_text, "parsed with Tesseract OCR; expect imperfect text"
    return None, None


def _compose_user_feedback_text(
    message: AgentMessage,
    *,
    review_results_prefix: str | None,
    interruption_prefix: str | None,
) -> str:
    prefixes = [prefix for prefix in (interruption_prefix, review_results_prefix) if isinstance(prefix, str) and prefix.strip()]
    if not prefixes:
        return message.content_markdown
    feedback = message.content_markdown.strip() or "(none)"
    return f"{'\n\n'.join(prefixes)}\n\nUser feedback:\n{feedback}"


def _build_entity_category_context(db: Session) -> str | None:
    records = list_term_name_description_pairs(db, taxonomy_key="entity_category")
    if not records:
        return None

    lines: list[str] = []
    for name, description in records:
        if description:
            lines.append(f"- {name}: {description}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines)


def build_user_content(
    message: AgentMessage,
    *,
    review_results_prefix: str | None = None,
    interruption_prefix: str | None = None,
    include_pdf_page_images: bool = True,
) -> str | list[dict[str, Any]]:
    content_text = _compose_user_feedback_text(
        message,
        review_results_prefix=review_results_prefix,
        interruption_prefix=interruption_prefix,
    )
    if not message.attachments:
        return content_text

    parts = assemble_attachment_parts(
        message.attachments,
        options=AttachmentAssemblyOptions(
            include_pdf_page_images=include_pdf_page_images,
            pdf_text_extractor=_extract_pdf_text_for_model,
            pdf_page_image_renderer=_pdf_page_image_data_urls,
        ),
    )

    if content_text.strip():
        parts.append({"type": "text", "text": content_text})
    if parts:
        return parts
    return content_text or "User sent attachments."


def _review_window_actions(
    db: Session,
    *,
    thread_id: str,
    start_exclusive: datetime | None,
    end_inclusive: datetime,
) -> list[AgentReviewAction]:
    stmt = (
        select(AgentReviewAction)
        .join(AgentChangeItem, AgentChangeItem.id == AgentReviewAction.change_item_id)
        .join(AgentRun, AgentRun.id == AgentChangeItem.run_id)
        .where(
            AgentRun.thread_id == thread_id,
            AgentReviewAction.created_at <= end_inclusive,
        )
        .options(selectinload(AgentReviewAction.change_item))
        .order_by(AgentReviewAction.created_at.asc())
    )
    if start_exclusive is not None:
        stmt = stmt.where(AgentReviewAction.created_at > start_exclusive)
    return list(db.scalars(stmt))


def _proposal_tool_name_for_change_type(change_type_value: str) -> str:
    return proposal_metadata_for_change_type(change_type_value).proposal_tool_name


def _proposal_tool_calls_for_runs(
    db: Session,
    *,
    run_ids: list[str],
    tool_names: set[str],
) -> dict[tuple[str, str], list[AgentToolCall]]:
    if not run_ids or not tool_names:
        return {}
    calls = list(
        db.scalars(
            select(AgentToolCall)
            .where(
                AgentToolCall.run_id.in_(run_ids),
                AgentToolCall.tool_name.in_(tool_names),
            )
            .order_by(AgentToolCall.created_at.asc())
        )
    )
    by_key: dict[tuple[str, str], list[AgentToolCall]] = {}
    for call in calls:
        key = (call.run_id, call.tool_name)
        by_key.setdefault(key, []).append(call)
    return by_key


def _pick_source_tool_call(
    *,
    item: AgentChangeItem,
    tool_name: str,
    candidates: dict[tuple[str, str], list[AgentToolCall]],
    used_call_ids: set[str],
) -> AgentToolCall | None:
    run_id = item.run_id
    pool = candidates.get((run_id, tool_name), [])
    if not pool:
        return None

    # Prefer the first unused call created at/after the change item; fallback to first unused.
    for call in pool:
        if call.id in used_call_ids:
            continue
        if call.created_at >= item.created_at:
            used_call_ids.add(call.id)
            return call
    for call in pool:
        if call.id in used_call_ids:
            continue
        used_call_ids.add(call.id)
        return call
    return None


def _build_review_results_prefix_for_current_turn(
    db: Session,
    *,
    thread_id: str,
    history: list[AgentMessage],
    current_user_message_id: str | None,
) -> str | None:
    if not current_user_message_id:
        return None

    current_user = next(
        (
            message
            for message in history
            if message.id == current_user_message_id and message.role == AgentMessageRole.USER
        ),
        None,
    )
    if current_user is None:
        return None

    previous_user_messages = [
        message
        for message in history
        if message.role == AgentMessageRole.USER and message.created_at < current_user.created_at
    ]
    start_exclusive = previous_user_messages[-1].created_at if previous_user_messages else None

    actions = _review_window_actions(
        db,
        thread_id=thread_id,
        start_exclusive=start_exclusive,
        end_inclusive=current_user.created_at,
    )
    if not actions:
        return None

    run_ids = sorted({action.change_item.run_id for action in actions if action.change_item is not None})
    tool_names = {
        _proposal_tool_name_for_change_type(action.change_item.change_type.value)
        for action in actions
        if action.change_item is not None
    }
    calls_by_key = _proposal_tool_calls_for_runs(db, run_ids=run_ids, tool_names=tool_names)
    used_call_ids: set[str] = set()

    lines = ["Review results from your previous proposals:"]
    ordinal = 1

    def _payload_override_summary(note: str | None) -> str | None:
        if not note:
            return None
        for segment in (part.strip() for part in note.split("|")):
            if segment.startswith("payload_override:"):
                return segment.removeprefix("payload_override:").strip() or None
        return None

    for action in actions:
        item = action.change_item
        if item is None:
            continue
        source_call = _pick_source_tool_call(
            item=item,
            tool_name=_proposal_tool_name_for_change_type(item.change_type.value),
            candidates=calls_by_key,
            used_call_ids=used_call_ids,
        )
        source_output_json = (
            source_call.output_json
            if source_call is not None and isinstance(source_call.output_json, dict)
            else {}
        )
        proposal_id = source_output_json.get("proposal_id") or item.id
        short_id = proposal_id[:8]
        note = item.review_note or action.note
        override_summary = _payload_override_summary(note)
        tool_name = _proposal_tool_name_for_change_type(item.change_type.value)
        lines.append(
            f"{ordinal}. {tool_name} proposal_id={proposal_id} proposal_short_id={short_id} "
            f"review_action={action.action.value} review_item_status={item.status.value} "
            f"review_note={note or '(none)'}"
            + (f" review_override={override_summary}" if override_summary else "")
        )
        ordinal += 1

    if ordinal == 1:
        return None
    return "\n".join(lines)


def _build_interruption_prefix_for_current_turn(
    db: Session,
    *,
    thread_id: str,
    history: list[AgentMessage],
    current_user_message_id: str | None,
) -> str | None:
    if not current_user_message_id:
        return None

    current_user = next(
        (
            message
            for message in history
            if message.id == current_user_message_id and message.role == AgentMessageRole.USER
        ),
        None,
    )
    if current_user is None:
        return None

    previous_user = next(
        (
            message
            for message in reversed(history)
            if message.role == AgentMessageRole.USER and message.created_at < current_user.created_at
        ),
        None,
    )
    if previous_user is None:
        return None

    candidate_runs = list(
        db.scalars(
            select(AgentRun)
            .where(
                AgentRun.thread_id == thread_id,
                AgentRun.user_message_id == previous_user.id,
            )
            .order_by(AgentRun.created_at.desc())
        )
    )
    interrupted_run = next(
        (
            run
            for run in candidate_runs
            if run.status == AgentRunStatus.FAILED
            and run.assistant_message_id is None
            and "interrupt" in (run.error_text or "").lower()
        ),
        None,
    )
    if interrupted_run is None:
        return None

    previous_feedback = " ".join(previous_user.content_markdown.split()).strip()
    if len(previous_feedback) > 180:
        previous_feedback = f"{previous_feedback[:177]}..."
    previous_feedback_line = (
        f'Interrupted previous user request: "{previous_feedback}"'
        if previous_feedback
        else "Interrupted previous user request: (no text; attachments and context still apply)."
    )

    return (
        "Previous turn note: the user interrupted your previous response before it completed.\n"
        f"{previous_feedback_line}\n"
        "Treat that interrupted request as conversation context while answering the latest user feedback."
    )


def build_llm_messages(
    db: Session,
    thread_id: str,
    *,
    current_user_message_id: str | None = None,
) -> list[dict[str, Any]]:
    settings = resolve_runtime_settings(db)
    include_pdf_page_images = _model_supports_vision(settings.agent_model)

    history = list(
        db.scalars(
            select(AgentMessage)
            .where(AgentMessage.thread_id == thread_id)
            .options(selectinload(AgentMessage.attachments))
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
                    current_user_context=_build_current_user_context(db),
                    entity_category_context=_build_entity_category_context(db),
                    user_memory=settings.user_memory,
                    current_timezone=get_settings().current_user_timezone,
                )
            ),
        }
    ]
    for message in history:
        if message.role == AgentMessageRole.USER:
            message_review_prefix = review_results_prefix if message.id == current_user_message_id else None
            message_interruption_prefix = interruption_prefix if message.id == current_user_message_id else None
            messages.append(
                {
                    "role": "user",
                    "content": build_user_content(
                        message,
                        review_results_prefix=message_review_prefix,
                        interruption_prefix=message_interruption_prefix,
                        include_pdf_page_images=include_pdf_page_images,
                    ),
                }
            )
            continue
        if message.role == AgentMessageRole.ASSISTANT:
            messages.append({"role": "assistant", "content": message.content_markdown})
            continue
        messages.append({"role": "system", "content": message.content_markdown})
    return messages
