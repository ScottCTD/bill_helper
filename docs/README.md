# Documentation Index

This directory is the canonical human-facing knowledge base for the current system.

Use the docs in layers:

1. `README.md` for onboarding and the dev loop.
2. `docs/architecture.md` for the system mental model.
3. `docs/repository-structure.md` for the filesystem map.
4. `docs/backend_index.md`, `docs/frontend_index.md`, `docs/ios_index.md`, `docs/telegram_index.md`, `docs/api.md`, and `docs/data-model.md` for subsystem entry points.
5. `../backend/docs/`, `../frontend/docs/`, `../ios/docs/`, `../telegram/docs/`, `docs/api/`, and `docs/features/` for focused subsystem docs.
6. `../tasks/` for active implementation tracking and `completed_tasks/` for archived task history.

## Stable Reference Docs

- `architecture.md`: system topology, boundaries, and major design choices.
- `repository-structure.md`: filesystem map and ownership boundaries.
- `backend_index.md`: backend index linking to focused backend docs under `../backend/docs/`.
- `../backend/docs/README.md`: backend topic map.
- `frontend_index.md`: frontend index linking to focused frontend docs under `../frontend/docs/`.
- `../frontend/docs/README.md`: frontend topic map.
- `ios_index.md`: iOS index linking to `../ios/README.md` and `../ios/docs/`.
- `telegram_index.md`: Telegram index linking to `../telegram/README.md` and `../telegram/docs/`.
- `api.md`: API index for `/api/v1`.
- `api/README.md`: API route-family topic map.
- `data-model.md`: schema and domain-model rules.
- `development.md`: setup, commands, and contributor workflow.
- `documentation-system.md`: doc ownership rules and anti-drift process.
- `features/README.md`: cross-cutting feature-doc index.
- `features/entry-lifecycle.md`: focused entry-domain flow map.
- `features/dashboard-analytics.md`: focused dashboard analytics flow map.
- `features/account-reconciliation.md`: focused account reconciliation flow map.
- `agent-billing-assistant.md`: billing assistant prompt/tool design notes.
- `adr/README.md`: ADR index and process.

## Task Tracking And Archive

- `../tasks/*.md`: active proposals, migration notes, and temporary caveats.
- `../tasks/2026-03-09_agent_surface_followup.md`: deferred cleanup task for agent surface policy and ownership boundaries.
- `completed_tasks/README.md`: archive conventions for completed task docs.
- `completed_tasks/*.md`: archived implementation tasks, retrospectives, and fix logs.
- `completed_tasks/2026-03-09_parallel_agent_thread.md`: archived task for thread-scoped agent composer controls and parallel thread activity UX.
- `completed_tasks/2026-03-09_entry_entity_label_repair_and_agent_selector_fix.md`: archived fix log for entry entity-label repair, agent selector hardening, and local data cleanup.
- `completed_tasks/2026-03-10_markdown_editor_vite_fix_log.md`: archived fix log for the BlockNote markdown editor fallback, Vite dep-cache restart bug, and dev-mode diagnostics.
- `completed_tasks/2026-03-11_interval_reconciliation.md`: archived task for interval-based account reconciliation, snapshot workflows, and review-gated agent snapshot proposals.
- `completed_tasks/2026-03-05_clean_architecture_fix_log.md`: archived desloppify and refactor fix log.
- `completed_tasks/2026-03-09_desloppify_fix_log.md`: archived March 9 desloppify cleanup log.
- `completed_tasks/2026-03-07_agent_thread_rename_ui_fix_log.md`: archived debug log for the agent thread inline-rename UI polish fixes.

Active tasks and completed task archives are not source-of-truth for current behavior. Promote stable conclusions back into the canonical docs above.

## Local Pointer Docs

- `../backend/README.md`: backend-local navigation and change checklist.
- `../backend/docs/README.md`: backend package-local canonical topic map.
- `../frontend/README.md`: frontend-local navigation and change checklist.
- `../frontend/docs/README.md`: frontend package-local canonical topic map.
- `../ios/README.md`: iOS local overview, run loop, and verification commands.
- `../ios/docs/README.md`: iOS package-local canonical topic map.
- `../telegram/README.md`: Telegram transport local overview, run/config notes, and links to `telegram/docs/`.
- `../telegram/docs/README.md`: Telegram package-local canonical topic map.

The package-local `backend/docs/` and `frontend/docs/` directories are canonical for subsystem behavior. The package-root READMEs stay close to the code as thin navigators and should not duplicate cross-repo architecture.

## Naming Rule

Task files must use a date prefix: `YYYY-MM-DD_slug.md`.
