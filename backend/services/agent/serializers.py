from __future__ import annotations

from backend.models import (
    AgentChangeItem,
    AgentMessage,
    AgentMessageAttachment,
    AgentReviewAction,
    AgentRunEvent,
    AgentRun,
    AgentThread,
    AgentToolCall,
)
from backend.schemas import (
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


def tool_call_to_schema(tool_call: AgentToolCall) -> AgentToolCallRead:
    return AgentToolCallRead(
        id=tool_call.id,
        run_id=tool_call.run_id,
        llm_tool_call_id=tool_call.llm_tool_call_id,
        tool_name=tool_call.tool_name,
        input_json=tool_call.input_json,
        output_json=tool_call.output_json,
        output_text=tool_call.output_text,
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


def run_to_schema(run: AgentRun) -> AgentRunRead:
    costs = calculate_usage_costs(
        model_name=run.model_name,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
    )
    return AgentRunRead(
        id=run.id,
        thread_id=run.thread_id,
        user_message_id=run.user_message_id,
        assistant_message_id=run.assistant_message_id,
        status=run.status,
        model_name=run.model_name,
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
        tool_calls=[tool_call_to_schema(call) for call in run.tool_calls],
        change_items=[change_item_to_schema(item) for item in run.change_items],
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
) -> AgentThreadSummaryRead:
    return AgentThreadSummaryRead(
        id=thread.id,
        title=thread.title,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
        last_message_preview=last_message_preview,
        pending_change_count=pending_change_count,
    )
