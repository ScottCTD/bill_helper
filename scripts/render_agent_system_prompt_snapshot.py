#!/usr/bin/env python3
# CALLING SPEC:
# - Purpose: render a fully expanded agent system prompt snapshot from the current database state.
# - Inputs: CLI args for output path, surface, date, timezone, and optional user selection.
# - Outputs: writes a markdown snapshot doc to disk and prints the output path.
# - Side effects: reads the configured database and writes one markdown file.
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from backend.database import open_session
from backend.models_finance import User
from backend.services.agent.message_history_content import build_entity_category_context
from backend.services.agent.prompts import SystemPromptContext, system_prompt
from backend.services.agent.user_context import build_current_user_context
from backend.services.runtime_settings import resolve_runtime_settings


@dataclass(frozen=True, slots=True)
class RenderInputs:
    response_surface: str
    current_date: date
    timezone_name: str
    selected_user_name: str
    account_context: str
    entity_category_context: str | None
    user_memory: list[str] | None
    rendered_prompt: str


def _default_output_path() -> Path:
    return Path("docs/features/system_prompt_example.md")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render the current agent system prompt to a markdown snapshot doc.")
    parser.add_argument("--surface", default="app", help="Response surface to render. Defaults to app.")
    parser.add_argument(
        "--date",
        dest="date_text",
        default=None,
        help="Current date to inject in YYYY-MM-DD format. Defaults to today in local time.",
    )
    parser.add_argument(
        "--timezone",
        default="America/Toronto",
        help="Timezone name to inject. Defaults to America/Toronto.",
    )
    parser.add_argument(
        "--user-name",
        default="admin",
        help="User name whose account/entity context should be rendered. Defaults to admin.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output markdown path. Defaults to docs/features/system_prompt_example.md",
    )
    return parser.parse_args()


def _resolve_date(date_text: str | None) -> date:
    if date_text is None:
        return datetime.now().date()
    return date.fromisoformat(date_text)


def _load_render_inputs(*, user_name: str, current_date: date, timezone_name: str, response_surface: str) -> RenderInputs:
    with open_session() as db:
        selected_user = db.scalar(select(User).where(User.name == user_name))
        if selected_user is None:
            selected_user = db.scalar(select(User).order_by(User.created_at.asc()))
        resolved_user_name = selected_user.name if selected_user is not None else "(none)"
        resolved_user_id = selected_user.id if selected_user is not None else None
        account_context = build_current_user_context(
            db,
            user_id=resolved_user_id,
            user_name=resolved_user_name,
        )
        entity_category_context = build_entity_category_context(
            db,
            owner_user_id=resolved_user_id,
        )
        settings = resolve_runtime_settings(db)
        rendered_prompt = system_prompt(
            SystemPromptContext(
                current_user_context=account_context,
                entity_category_context=entity_category_context,
                user_memory=settings.user_memory,
                current_date=current_date,
                current_timezone=timezone_name,
                response_surface=response_surface,
            )
        )
        return RenderInputs(
            response_surface=response_surface,
            current_date=current_date,
            timezone_name=timezone_name,
            selected_user_name=resolved_user_name,
            account_context=account_context,
            entity_category_context=entity_category_context,
            user_memory=settings.user_memory,
            rendered_prompt=rendered_prompt,
        )


def _build_snapshot_markdown(inputs: RenderInputs) -> str:
    markdown = (
        "# Rendered Agent System Prompt Snapshot\n\n"
        f"This doc snapshots the fully rendered agent system prompt from the current local database state for the "
        f"`{inputs.response_surface}` response surface on `{inputs.current_date.isoformat()}`.\n\n"
        "It is a rendered snapshot, not the canonical source of truth. The live source template remains "
        "`backend/services/agent/system_prompt.j2`, and the runtime renderer remains "
        "`backend/services/agent/prompts.py`.\n\n"
        "Rendered with:\n"
        f"- response surface: `{inputs.response_surface}`\n"
        f"- timezone: `{inputs.timezone_name}`\n"
        f"- current date: `{inputs.current_date.isoformat()}`\n"
        f"- selected user: `{inputs.selected_user_name}`\n"
        "- current user context: derived from the current local database\n"
        "- entity category context: derived from the current local database\n"
        "- user memory: derived from the current local database\n\n"
        "```md\n"
        f"{inputs.rendered_prompt}"
        "```\n"
    )
    return "\n".join(line.rstrip() for line in markdown.splitlines()) + "\n"


def main() -> int:
    args = _parse_args()
    current_date = _resolve_date(args.date_text)
    output_path = Path(args.output) if args.output is not None else _default_output_path()
    inputs = _load_render_inputs(
        user_name=args.user_name,
        current_date=current_date,
        timezone_name=args.timezone,
        response_surface=args.surface,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_build_snapshot_markdown(inputs), encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
