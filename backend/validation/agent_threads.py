from __future__ import annotations

THREAD_TITLE_MAX_LENGTH = 80
THREAD_TITLE_MAX_WORDS = 5


class AgentThreadTitleError(ValueError):
    pass


def normalize_thread_title(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).strip()
    return normalized or None


def validate_thread_title(value: str) -> str:
    normalized = normalize_thread_title(value)
    if normalized is None:
        raise AgentThreadTitleError("thread title cannot be empty")
    if len(normalized) > THREAD_TITLE_MAX_LENGTH:
        raise AgentThreadTitleError(
            f"thread title must be {THREAD_TITLE_MAX_LENGTH} characters or fewer"
        )
    if len(normalized.split()) > THREAD_TITLE_MAX_WORDS:
        raise AgentThreadTitleError(
            f"thread title must be {THREAD_TITLE_MAX_WORDS} words or fewer"
        )
    return normalized
