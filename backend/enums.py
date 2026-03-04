from __future__ import annotations

from enum import StrEnum


class EntryKind(StrEnum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"
    TRANSFER = "TRANSFER"


class LinkType(StrEnum):
    RECURRING = "RECURRING"
    SPLIT = "SPLIT"
    BUNDLE = "BUNDLE"


class AgentMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentToolCallStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    CANCELLED = "cancelled"


class AgentRunEventType(StrEnum):
    RUN_STARTED = "run_started"
    REASONING_UPDATE = "reasoning_update"
    TOOL_CALL_QUEUED = "tool_call_queued"
    TOOL_CALL_STARTED = "tool_call_started"
    TOOL_CALL_COMPLETED = "tool_call_completed"
    TOOL_CALL_FAILED = "tool_call_failed"
    TOOL_CALL_CANCELLED = "tool_call_cancelled"
    RUN_COMPLETED = "run_completed"
    RUN_FAILED = "run_failed"


class AgentRunEventSource(StrEnum):
    MODEL_REASONING = "model_reasoning"
    ASSISTANT_CONTENT = "assistant_content"
    TOOL_CALL = "tool_call"


class AgentChangeType(StrEnum):
    CREATE_ENTRY = "create_entry"
    UPDATE_ENTRY = "update_entry"
    DELETE_ENTRY = "delete_entry"
    CREATE_TAG = "create_tag"
    UPDATE_TAG = "update_tag"
    DELETE_TAG = "delete_tag"
    CREATE_ENTITY = "create_entity"
    UPDATE_ENTITY = "update_entity"
    DELETE_ENTITY = "delete_entity"


class AgentChangeStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    APPLY_FAILED = "APPLY_FAILED"


class AgentReviewActionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
