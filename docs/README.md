# Documentation Index

This directory is the canonical human-facing knowledge base for the current system.

Use the docs in layers:

1. `README.md` for onboarding and the dev loop.
2. `docs/architecture.md` for the system mental model.
3. `docs/repository_structure.md` for the filesystem map.
4. `docs/backend_index.md`, `docs/frontend_index.md`, `docs/ios_index.md`, `docs/telegram_index.md`, `docs/api.md`, and `docs/data_model.md` for subsystem entry points.
5. `../backend/docs/`, `../frontend/docs/`, `../ios/docs/`, `../telegram/docs/`, `docs/api/`, and `docs/features/` for focused subsystem docs.
6. `../tasks/` for active implementation tracking and `completed_tasks/` for archived task history.

## Stable Reference Docs

- `architecture.md`: system topology, boundaries, and major design choices.
- `repository_structure.md`: filesystem map and ownership boundaries.
- `backend_index.md`: backend index linking to focused backend docs under `../backend/docs/`.
- `../backend/docs/README.md`: backend topic map.
- `frontend_index.md`: frontend index linking to focused frontend docs under `../frontend/docs/`.
- `../frontend/docs/README.md`: frontend topic map.
- `ios_index.md`: iOS index linking to `../ios/README.md` and `../ios/docs/`.
- `telegram_index.md`: Telegram index linking to `../telegram/README.md` and `../telegram/docs/`.
- `api.md`: API index for `/api/v1`.
- `api/README.md`: API route-family topic map.
- `data_model.md`: schema and domain-model rules.
- `development.md`: setup, commands, and contributor workflow.
- `documentation_system.md`: doc ownership rules and anti-drift process.
- `features/README.md`: cross-cutting feature-doc index.
- `features/entry_lifecycle.md`: focused entry-domain flow map.
- `features/dashboard_analytics.md`: focused dashboard analytics flow map.
- `features/account_reconciliation.md`: focused account reconciliation flow map.
- `agent_billing_assistant.md`: billing assistant prompt/tool design notes.
- `adr/README.md`: ADR index and process.

## Task Tracking And Archive

- `../tasks/*.md`: active proposals, migration notes, and temporary caveats.
- `completed_tasks/README.md`: archive conventions for completed task docs.
- `completed_tasks/*.md`: archived implementation tasks, retrospectives, and fix logs.

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

Task files must use a date prefix: `YYYY_MM_DD-task_name.md`.
