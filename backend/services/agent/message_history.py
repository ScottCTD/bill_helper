from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from backend.enums import AgentMessageRole
from backend.models import Account, AgentChangeItem, AgentMessage, AgentReviewAction, AgentRun, AgentToolCall, User
from backend.services.agent.prompts import system_prompt
from backend.services.runtime_settings import resolve_runtime_settings


def attachment_to_data_url(file_path: str, mime_type: str) -> str | None:
    path = Path(file_path)
    if not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _compose_user_feedback_text(message: AgentMessage, review_results_prefix: str | None) -> str:
    if review_results_prefix is None:
        return message.content_markdown
    feedback = message.content_markdown.strip() or "(none)"
    return f"{review_results_prefix}\n\nUser feedback:\n{feedback}"


def _build_current_user_context(db: Session) -> str:
    settings = resolve_runtime_settings(db)
    current_user_name = (settings.current_user_name or "").strip() or "(unknown)"
    accounts = list(
        db.scalars(
            select(Account)
            .join(User, User.id == Account.owner_user_id)
            .where(func.lower(User.name) == current_user_name.lower())
            .options(selectinload(Account.entity))
            .order_by(Account.created_at.asc())
        )
    )

    lines = [
        f"user_name: {current_user_name}",
        f"accounts_count: {len(accounts)}",
        "accounts:",
    ]
    if not accounts:
        lines.append("- (none)")
        return "\n".join(lines)

    max_accounts = 40
    for index, account in enumerate(accounts[:max_accounts], start=1):
        status = "active" if account.is_active else "inactive"
        lines.append(
            f"- {index}. name={account.name}; currency={account.currency_code}; status={status}; "
            f"type={account.account_type or '-'}; institution={account.institution or '-'}; "
            f"entity={account.entity.name if account.entity is not None else '-'}"
        )
    if len(accounts) > max_accounts:
        lines.append(f"- ... (+{len(accounts) - max_accounts} more)")
    return "\n".join(lines)


def build_user_content(
    message: AgentMessage,
    *,
    review_results_prefix: str | None = None,
) -> str | list[dict[str, Any]]:
    content_text = _compose_user_feedback_text(message, review_results_prefix)
    if not message.attachments:
        return content_text

    parts: list[dict[str, Any]] = []
    if content_text.strip():
        parts.append({"type": "text", "text": content_text})
    for attachment in message.attachments:
        data_url = attachment_to_data_url(attachment.file_path, attachment.mime_type)
        if data_url is None:
            continue
        parts.append({"type": "image_url", "image_url": {"url": data_url}})
    if not parts:
        return content_text or "User sent image attachments."
    return parts


def _compact_json(value: Any, *, max_len: int = 600) -> str:
    try:
        text = json.dumps(value, ensure_ascii=True, sort_keys=True)
    except TypeError:
        text = str(value)
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 3]}..."


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
    return {
        "create_tag": "propose_create_tag",
        "update_tag": "propose_update_tag",
        "delete_tag": "propose_delete_tag",
        "create_entity": "propose_create_entity",
        "update_entity": "propose_update_entity",
        "delete_entity": "propose_delete_entity",
        "create_entry": "propose_create_entry",
        "update_entry": "propose_update_entry",
        "delete_entry": "propose_delete_entry",
    }.get(change_type_value, "proposal_tool_result")


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
    for action in actions:
        item = action.change_item
        if item is None:
            continue
        source_tool_name = _proposal_tool_name_for_change_type(item.change_type.value)
        source_call = _pick_source_tool_call(
            item=item,
            tool_name=source_tool_name,
            candidates=calls_by_key,
            used_call_ids=used_call_ids,
        )
        source_arguments = (
            source_call.input_json
            if source_call is not None and isinstance(source_call.input_json, dict)
            else item.payload_json
        )
        source_output_json = (
            source_call.output_json
            if source_call is not None and isinstance(source_call.output_json, dict)
            else {"status": "OK", "summary": "proposal created"}
        )
        lines.append(
            f"{ordinal}. {source_tool_name} args={_compact_json(source_arguments, max_len=220)}"
        )
        summary = source_output_json.get("summary")
        if summary is not None:
            lines.append(f"   proposal_summary: {summary}")
        lines.extend(
            [
                f"   review_action: {action.action.value}",
                f"   review_item_status: {item.status.value}",
                f"   review_note: {item.review_note or '(none)'}",
                f"   action_note: {action.note or '(none)'}",
            ]
        )
        ordinal += 1

    if ordinal == 1:
        return None
    return "\n".join(lines)


def build_llm_messages(
    db: Session,
    thread_id: str,
    *,
    current_user_message_id: str | None = None,
) -> list[dict[str, Any]]:
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

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt(current_user_context=_build_current_user_context(db))}
    ]
    for message in history:
        if message.role == AgentMessageRole.USER:
            message_review_prefix = review_results_prefix if message.id == current_user_message_id else None
            messages.append(
                {
                    "role": "user",
                    "content": build_user_content(message, review_results_prefix=message_review_prefix),
                }
            )
            continue
        if message.role == AgentMessageRole.ASSISTANT:
            messages.append({"role": "assistant", "content": message.content_markdown})
            continue
        messages.append({"role": "system", "content": message.content_markdown})
    return messages
