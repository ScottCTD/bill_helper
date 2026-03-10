# Completed Tasks Archive

This directory stores archived task docs after active work in `/tasks/*.md` is finished.

## Layout

- `../tasks/*.md`: active implementation tasks, migration notes, and temporary caveats.
- `*.md`: completed tasks, retrospectives, and archived fix logs kept for historical context.

## Rules

- Name files `YYYY-MM-DD_slug.md`.
- Keep each task doc focused on one change or refactor.
- When work lands, update the canonical docs in the stable `docs/` tree.
- Do not leave stable behavior documented only in a task doc or archive entry.

## Recent Archived Tasks

- `2026-03-09_parallel_agent_thread.md`: archived task for thread-scoped agent composer controls and parallel thread activity UX.
- `2026-03-09_entry_entity_label_repair_and_agent_selector_fix.md`: archived fix log for entry entity-label corruption and agent update selector approval failures.
- `2026-03-10_markdown_editor_vite_fix_log.md`: archived fix log for the BlockNote markdown editor runtime/import failures and Vite dep-cache restart hardening.
- `2026-03-08_telegram_bot_todo.md`: archived Telegram integration implementation task.
- `2026-03-05_clean_architecture_fix_log.md`: archived desloppify and architecture fix log.
