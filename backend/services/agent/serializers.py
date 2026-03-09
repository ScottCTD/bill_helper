from __future__ import annotations

import logging
import re
from typing import Any

from backend.enums_agent import is_supported_agent_change_type
from backend.models_agent import (
    AgentChangeItem,
    AgentMessage,
    AgentMessageAttachment,
    AgentReviewAction,
    AgentRunEvent,
    AgentRun,
    AgentThread,
    AgentToolCall,
)
from backend.schemas_agent import (
    AgentChangeItemRead,
    AgentMessageAttachmentRead,
    AgentMessageRead,
    AgentReviewActionRead,
    AgentRunEventRead,
    AgentRunRead,
    AgentThreadRead,
    AgentThreadSummaryRead,
    AgentToolCallRead,
)
from backend.services.agent.pricing import calculate_usage_costs


logger = logging.getLogger(__name__)


_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MARKDOWN_HEADING_PATTERN = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MARKDOWN_BLOCKQUOTE_PATTERN = re.compile(r"^\s*>\s?", re.MULTILINE)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:[a-zA-Z0-9_+.-]+)?\n?|```")


def _format_terminal_assistant_reply(content: str | None, *, surface: str) -> str | None:
    if content is None:
        return None
    if surface != "telegram":
        return content

    formatted = _MARKDOWN_LINK_PATTERN.sub(r"\1 (\2)", content)
    formatted = _MARKDOWN_HEADING_PATTERN.sub("", formatted)
    formatted = _MARKDOWN_BLOCKQUOTE_PATTERN.sub("", formatted)
    formatted = _MARKDOWN_FENCE_PATTERN.sub("", formatted)
    formatted = (
        formatted.replace("**", "")
        .replace("__", "")
        .replace("~~", "")
        .replace("`", "")
    )
    formatted = re.sub(r"\n{3,}", "\n\n", formatted).strip()
    return formatted or None


def attachment_to_schema(attachment: AgentMessageAttachment, *, api_prefix: str) -> AgentMessageAttachmentRead:
    return AgentMessageAttachmentRead(
        id=attachment.id,
        message_id=attachment.message_id,
        mime_type=attachment.mime_type,
        file_path=attachment.file_path,
        attachment_url=f"{api_prefix}/agent/attachments/{attachment.id}",
        created_at=attachment.created_at,
    )


def message_to_schema(message: AgentMessage, *, api_prefix: str) -> AgentMessageRead:
    return AgentMessageRead(
        id=message.id,
        thread_id=message.thread_id,
        role=message.role,
        content_markdown=message.content_markdown,
        created_at=message.created_at,
        attachments=[attachment_to_schema(attachment, api_prefix=api_prefix) for attachment in message.attachments],
    )


def tool_call_to_schema(tool_call: AgentToolCall, *, include_payload: bool = True) -> AgentToolCallRead:
    return AgentToolCallRead(
        id=tool_call.id,
        run_id=tool_call.run_id,
        llm_tool_call_id=tool_call.llm_tool_call_id,
        tool_name=tool_call.tool_name,
        input_json=tool_call.input_json if include_payload else None,
        output_json=tool_call.output_json if include_payload else None,
        output_text=tool_call.output_text if include_payload else None,
        has_full_payload=include_payload,
        status=tool_call.status,
        created_at=tool_call.created_at,
        started_at=tool_call.started_at,
        completed_at=tool_call.completed_at,
    )


def run_event_to_schema(event: AgentRunEvent) -> AgentRunEventRead:
    return AgentRunEventRead(
        id=event.id,
        run_id=event.run_id,
        sequence_index=event.sequence_index,
        event_type=event.event_type,
        source=event.source,
        message=event.message,
        tool_call_id=event.tool_call_id,
        created_at=event.created_at,
    )


def _tool_call_for_stream_event(
    run: AgentRun,
    event: AgentRunEvent,
    *,
    tool_call: AgentToolCall | None = None,
) -> AgentToolCall | None:
    if tool_call is not None:
        return tool_call
    if event.tool_call is not None:
        return event.tool_call
    if event.tool_call_id is None:
        return None
    return next((call for call in run.tool_calls if call.id == event.tool_call_id), None)


def stream_run_event_to_payload(
    run: AgentRun,
    event: AgentRunEvent,
    *,
    tool_call: AgentToolCall | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": "run_event",
        "run_id": run.id,
        "event": run_event_to_schema(event).model_dump(mode="json"),
    }
    compact_tool_call = _tool_call_for_stream_event(run, event, tool_call=tool_call)
    if compact_tool_call is not None:
        payload["tool_call"] = tool_call_to_schema(
            compact_tool_call,
            include_payload=False,
        ).model_dump(mode="json")
    return payload


def review_action_to_schema(action: AgentReviewAction) -> AgentReviewActionRead:
    return AgentReviewActionRead(
        id=action.id,
        change_item_id=action.change_item_id,
        action=action.action,
        actor=action.actor,
        note=action.note,
        created_at=action.created_at,
    )


def change_item_to_schema(item: AgentChangeItem) -> AgentChangeItemRead:
    return AgentChangeItemRead(
        id=item.id,
        run_id=item.run_id,
        change_type=item.change_type,
        payload_json=item.payload_json,
        rationale_text=item.rationale_text,
        status=item.status,
        review_note=item.review_note,
        applied_resource_type=item.applied_resource_type,
        applied_resource_id=item.applied_resource_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        review_actions=[review_action_to_schema(action) for action in item.review_actions],
    )


def _serializable_change_items(run: AgentRun) -> list[AgentChangeItem]:
    supported_items: list[AgentChangeItem] = []
    for item in run.change_items:
        if is_supported_agent_change_type(item.change_type):
            supported_items.append(item)
            continue
        logger.warning(
            "Skipping unsupported agent change item from API response: scope=agent_run_serializer run_id=%s change_item_id=%s change_type=%s status=%s",
            run.id,
            item.id,
            item.change_type.name,
            item.status.value,
        )
    return supported_items


def run_to_schema(
    run: AgentRun,
    *,
    include_tool_payload: bool = True,
    surface: str | None = None,
) -> AgentRunRead:
    costs = calculate_usage_costs(
        model_name=run.model_name,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cache_read_tokens=run.cache_read_tokens,
        cache_write_tokens=run.cache_write_tokens,
    )
    reply_surface = surface or run.surface or "app"
    assistant_content = run.assistant_message.content_markdown if run.assistant_message is not None else None
    return AgentRunRead(
        id=run.id,
        thread_id=run.thread_id,
        user_message_id=run.user_message_id,
        assistant_message_id=run.assistant_message_id,
        terminal_assistant_reply=_format_terminal_assistant_reply(
            assistant_content,
            surface=reply_surface,
        ),
        status=run.status,
        model_name=run.model_name,
        surface=run.surface,
        reply_surface=reply_surface,
        context_tokens=run.context_tokens,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cache_read_tokens=run.cache_read_tokens,
        cache_write_tokens=run.cache_write_tokens,
        input_cost_usd=costs.input_cost_usd,
        output_cost_usd=costs.output_cost_usd,
        total_cost_usd=costs.total_cost_usd,
        error_text=run.error_text,
        created_at=run.created_at,
        completed_at=run.completed_at,
        events=[run_event_to_schema(event) for event in run.events],
        tool_calls=[tool_call_to_schema(call, include_payload=include_tool_payload) for call in run.tool_calls],
        change_items=[change_item_to_schema(item) for item in _serializable_change_items(run)],
    )


def thread_to_schema(thread: AgentThread) -> AgentThreadRead:
    return AgentThreadRead(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def thread_summary_to_schema(
    thread: AgentThread,
    *,
    last_message_preview: str | None,
    pending_change_count: int,
    has_running_run: bool,
) -> AgentThreadSummaryRead:
    return AgentThreadSummaryRead(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_message_preview=last_message_preview,
        pending_change_count=pending_change_count,
        has_running_run=has_running_run,
    )
