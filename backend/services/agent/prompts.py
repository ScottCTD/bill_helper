from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment, StrictUndefined

DEFAULT_USER_TIMEZONE = "America/Toronto"

_PROMPT_TEMPLATE_ENV = Environment(
    autoescape=False,
    trim_blocks=False,
    lstrip_blocks=False,
    keep_trailing_newline=True,
    undefined=StrictUndefined,
)

SYSTEM_PROMPT_TEMPLATE_NAME = "system_prompt.j2"


@lru_cache(maxsize=1)
def _system_prompt_template():
    template_text = files("backend.services.agent").joinpath(SYSTEM_PROMPT_TEMPLATE_NAME).read_text(
        encoding="utf-8"
    )
    return _PROMPT_TEMPLATE_ENV.from_string(template_text)


def _resolve_prompt_timezone(timezone_name: str | None) -> tuple[str, ZoneInfo]:
    normalized = " ".join((timezone_name or "").split()).strip()
    candidate = normalized or DEFAULT_USER_TIMEZONE
    try:
        return candidate, ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        return DEFAULT_USER_TIMEZONE, ZoneInfo(DEFAULT_USER_TIMEZONE)


@dataclass(frozen=True, slots=True)
class SystemPromptContext:
    current_user_context: str | None = None
    entity_category_context: str | None = None
    user_memory: str | None = None
    current_date: date | None = None
    current_timezone: str | None = None


def system_prompt(context: SystemPromptContext | None = None) -> str:
    prompt_context = context or SystemPromptContext()
    account_context = (
        prompt_context.current_user_context.strip()
        if prompt_context.current_user_context is not None and prompt_context.current_user_context.strip()
        else "(none)"
    )
    user_memory_content = (
        prompt_context.user_memory.strip()
        if prompt_context.user_memory is not None and prompt_context.user_memory.strip()
        else "(none)"
    )
    entity_category_content = (
        prompt_context.entity_category_context.strip()
        if prompt_context.entity_category_context is not None and prompt_context.entity_category_context.strip()
        else "(none)"
    )
    timezone_name, timezone_info = _resolve_prompt_timezone(prompt_context.current_timezone)
    date_text = (prompt_context.current_date or datetime.now(timezone_info).date()).isoformat()
    return _system_prompt_template().render(
        timezone_name=timezone_name,
        date_text=date_text,
        account_context=account_context,
        user_memory_content=user_memory_content,
        entity_category_content=entity_category_content,
    )
