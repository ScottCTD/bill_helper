# Documentation Index

This directory is the canonical human-facing knowledge base for the current system.

Use the docs in layers:

1. `README.md` for onboarding and the dev loop.
2. `docs/architecture.md` for the system mental model.
3. `docs/repository-structure.md` for the filesystem map.
4. `docs/backend.md`, `docs/frontend.md`, `docs/api.md`, and `docs/data-model.md` for subsystem entry points.
5. `docs/backend/`, `docs/frontend/`, and `docs/api/` for focused subsystem docs.
6. `docs/exec-plans/` for active implementation plans and archived retrospectives.

## Stable Reference Docs

- `architecture.md`: system topology, boundaries, and major design choices.
- `repository-structure.md`: filesystem map and ownership boundaries.
- `backend.md`: backend index linking to focused backend docs under `backend/`.
- `backend/README.md`: backend topic map.
- `frontend.md`: frontend index linking to focused frontend docs under `frontend/`.
- `frontend/README.md`: frontend topic map.
- `api.md`: API index for `/api/v1`.
- `api/README.md`: API route-family topic map.
- `data-model.md`: schema and domain-model rules.
- `development.md`: setup, commands, and contributor workflow.
- `documentation-system.md`: doc ownership rules and anti-drift process.
- `feature-entry-lifecycle.md`: focused entry-domain flow map.
- `feature-dashboard-analytics.md`: focused dashboard analytics flow map.
- `feature-account-reconciliation.md`: focused account reconciliation flow map.
- `agent-billing-assistant.md`: billing assistant prompt/tool design notes.
- `adr/README.md`: ADR index and process.

## Execution Plans

- `exec-plans/README.md`: how to use active and completed plan docs.
- `exec-plans/active/*.md`: active proposals, migration notes, and temporary caveats.
- `exec-plans/completed/*.md`: archived implementation plans and retrospectives.
- `exec-plans/completed/2026-03-05_clean_architecture_fix_log.md`: archived desloppify and refactor fix log.
- `exec-plans/completed/2026-03-07_agent_thread_rename_ui_fix_log.md`: archived debug log for the agent thread inline-rename UI polish fixes.

Execution plans are not source-of-truth for current behavior. Promote stable conclusions back into the canonical docs above.

## Local Pointer Docs

- `../backend/README.md`: backend-local navigation and change checklist.
- `../frontend/README.md`: frontend-local navigation and change checklist.
- `../telegram/README.md`: Telegram transport local overview, run/config notes, and links to `telegram/docs/`.

These package-local READMEs stay close to the code and should point back to canonical docs instead of duplicating cross-repo architecture.

## Naming Rule

Execution-plan files must use a date prefix: `YYYY-MM-DD_slug.md`.
