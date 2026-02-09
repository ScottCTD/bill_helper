from __future__ import annotations

from enum import StrEnum


class EntryKind(StrEnum):
    EXPENSE = "EXPENSE"
    INCOME = "INCOME"


class LinkType(StrEnum):
    RECURRING = "RECURRING"
    SPLIT = "SPLIT"
    BUNDLE = "BUNDLE"
    RELATED = "RELATED"


class AgentMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class AgentRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentToolCallStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


class AgentChangeType(StrEnum):
    CREATE_ENTRY = "create_entry"
    CREATE_TAG = "create_tag"
    CREATE_ENTITY = "create_entity"


class AgentChangeStatus(StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    APPLY_FAILED = "APPLY_FAILED"


class AgentReviewActionType(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
