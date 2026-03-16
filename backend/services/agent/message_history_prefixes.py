# CALLING SPEC:
# - Purpose: implement focused service logic for `message_history_prefixes`.
# - Inputs: callers that import `backend/services/agent/message_history_prefixes.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `message_history_prefixes`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.enums_agent import AgentMessageRole, AgentRunStatus
from backend.models_agent import (
    AgentChangeItem,
    AgentMessage,
    AgentReviewAction,
    AgentRun,
)
from backend.services.agent.proposal_metadata import proposal_metadata_for_change_type


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


def _proposal_cli_command_for_change_type(change_type_value: str) -> str:
    return proposal_metadata_for_change_type(change_type_value).cli_command


def build_review_results_prefix_for_current_turn(
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
        proposal_id = item.id
        short_id = proposal_id[:8]
        note = item.review_note or action.note
        override_summary = _payload_override_summary(note)
        cli_command = _proposal_cli_command_for_change_type(item.change_type.value)
        lines.append(
            f"{ordinal}. {cli_command} proposal_id={proposal_id} proposal_short_id={short_id} "
            f"review_action={action.action.value} review_item_status={item.status.value} "
            f"review_note={note or '(none)'}"
            + (f" review_override={override_summary}" if override_summary else "")
        )
        ordinal += 1

    if ordinal == 1:
        return None
    return "\n".join(lines)


def build_interruption_prefix_for_current_turn(
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
