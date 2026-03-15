# CALLING SPEC:
# - Purpose: implement focused service logic for `prompts`.
# - Inputs: callers that import `backend/services/agent/prompts.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `prompts`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from importlib.resources import files
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from jinja2 import Environment, StrictUndefined

from backend.cli.reference import render_bh_cheat_sheet

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
    user_memory: list[str] | None = None
    current_date: date | None = None
    current_timezone: str | None = None
    response_surface: str | None = None


def _format_markdown_unordered_list(items: list[str] | None) -> str:
    if not items:
        return "(none)"
    return "\n".join(f"- {item}" for item in items)


def system_prompt(context: SystemPromptContext | None = None) -> str:
    prompt_context = context or SystemPromptContext()
    account_context = (
        prompt_context.current_user_context.strip()
        if prompt_context.current_user_context is not None and prompt_context.current_user_context.strip()
        else "(none)"
    )
    user_memory_content = _format_markdown_unordered_list(prompt_context.user_memory)
    entity_category_content = (
        prompt_context.entity_category_context.strip()
        if prompt_context.entity_category_context is not None and prompt_context.entity_category_context.strip()
        else "(none)"
    )
    timezone_name, timezone_info = _resolve_prompt_timezone(prompt_context.current_timezone)
    date_text = (prompt_context.current_date or datetime.now(timezone_info).date()).isoformat()
    return _system_prompt_template().render(
        response_surface=(prompt_context.response_surface or "app"),
        timezone_name=timezone_name,
        date_text=date_text,
        account_context=account_context,
        bh_cheat_sheet=render_bh_cheat_sheet(),
        user_memory_content=user_memory_content,
        entity_category_content=entity_category_content,
    )
