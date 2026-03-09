# Execution Plans

This directory is for volatile work-tracking docs, not for stable system reference.

## Layout

- `active/*.md`: current implementation plans, temporary caveats, migration checklists, and open execution notes.
- `completed/*.md`: finished plans, retrospectives, and archived fix logs kept for historical context.

## Rules

- Name files `YYYY-MM-DD_slug.md`.
- Keep plan docs focused on one change or refactor.
- When work lands, update the canonical docs in the stable `docs/` tree.
- Do not leave stable behavior documented only in an execution plan.
- Package READMEs and `AGENTS.md` should link here when work tracking is needed; they should not absorb plan content.

## Recent Active Plans

- `active/2026-03-09_agent_surface_followup.md`: deferred follow-up plan for reducing agent surface leakage across router, runtime, prompt, and serializer layers.

## Recent Archived Plans

- `completed/2026-03-08_telegram_bot_todo.md`: archived Telegram integration implementation plan.
