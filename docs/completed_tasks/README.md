# Completed Tasks Archive

This directory stores archived task docs after active work in `/tasks/*.md` is finished.

## Layout

- `../tasks/*.md`: active implementation tasks, migration notes, and temporary caveats.
- `*.md`: completed tasks, retrospectives, and archived fix logs kept for historical context.

## Rules

- Name files `YYYY_MM_DD-task_name.md`.
- Keep each task doc focused on one change or refactor.
- When work lands, update the canonical docs in the stable `docs/` tree.
- Do not leave stable behavior documented only in a task doc or archive entry.

## Recent Archived Tasks

- `2026_03_16-groups_member_cli_followup.md`: archived task; decision to keep `bh groups add-member` / `remove-member` JSON-only (no flag/subcommand UX for nested membership payloads).
- `2026_03_16-brittle_cli_create.md`: archived task for replacing brittle JSON-based `bh * create` commands with exact flag-based CLI interfaces and better create-command errors.
- `2026_03_16-dashboard_plot_improve.md`: dashboard chart and table improvements (Income vs Expense layout, Sankey, day-to-day bar plot, Monthly Spend table).
- `2026_03_03-agent_workspace.md`: archived task for canonical per-user files, durable attachment storage, and per-user Docker workspace provisioning.
- `2026_03_12_multi_user_security.md`: archived task for password-backed sessions, user-owned resource scoping, admin impersonation, and web auth flow migration.
- `2026_03_13-cli_unified_interface.md`: archived task for the `billengine` CLI, workspace terminal execution, and removal of the old model-visible CRUD tool catalog.
- `2026_03_09_parallel_agent_thread.md`: archived task for thread-scoped agent composer controls and parallel thread activity UX.
- `2026_03_09_entry_entity_label_repair_and_agent_selector_fix.md`: archived fix log for entry entity-label corruption and agent update selector approval failures.
- `2026_03_10_markdown_editor_vite_fix_log.md`: archived fix log for the BlockNote markdown editor runtime/import failures and Vite dep-cache restart hardening.
- `2026_03_11_interval_reconciliation.md`: archived task for interval-based account reconciliation, account-modal snapshot management, and snapshot proposal review.
- `2026_03_08_telegram_bot_todo.md`: archived Telegram integration implementation task.
- `2026_03_05_clean_architecture_fix_log.md`: archived desloppify and architecture fix log.
