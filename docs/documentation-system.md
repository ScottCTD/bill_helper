# Documentation System

The docs in this repository are intentionally layered. Do not use one file for every audience.

## Layers

- `README.md`: onboarding, local setup, run commands, and top-level links.
- `AGENTS.md`: short working agreement for coding agents, including editing and refactor standards plus links to the right docs.
- `docs/*.md`: canonical human-facing index and reference docs for current behavior.
- `backend/docs/*.md`, `frontend/docs/*.md`, `ios/docs/*.md`, `telegram/docs/*.md`, `docs/api/*.md`: focused subsystem docs owned by their packages, with API docs remaining under the shared canonical docs tree.
- `docs/features/*.md`: cross-cutting feature docs that span multiple packages or layers.
- `tasks/*.md`: active implementation plans, migration notes, and temporary caveats.
- `docs/completed_tasks/*.md`: archived task docs and retrospectives.
- `backend/README.md` and `frontend/README.md`: thin package-local navigation docs.
- Nested `AGENTS.md`: optional and path-scoped; only add when a subtree needs special editing rules.

## Boundary Rules

- System architecture belongs in `docs/architecture.md`, not in `AGENTS.md`.
- Filesystem mapping belongs in `docs/repository-structure.md`, not in package READMEs.
- Top-level subsystem files (`docs/backend_index.md`, `docs/frontend_index.md`, `docs/ios_index.md`, `docs/telegram_index.md`, `docs/api.md`) are indexes, not dumping grounds.
- Stable backend behavior belongs in `backend/docs/*.md`.
- Stable frontend behavior belongs in `frontend/docs/*.md`.
- API contracts belong in `docs/api/*.md`.
- Cross-cutting feature behavior belongs in `docs/features/*.md`.
- Temporary work notes, migration checklists, and refactor sequencing belong in `tasks/`.
- Historical task retrospectives and fix logs belong in `docs/completed_tasks/`.
- Package READMEs should help local navigation and point to canonical docs. They should not grow into parallel architecture docs.

## Source-of-Truth Matrix

| Topic | Primary Source | Secondary References |
| --- | --- | --- |
| Project setup and dev loop | `README.md` | `docs/development.md` |
| Documentation policy | `docs/documentation-system.md` | `AGENTS.md`, `docs/README.md` |
| System architecture | `docs/architecture.md` | ADRs, `docs/backend_index.md`, `docs/frontend_index.md` |
| Repository layout | `docs/repository-structure.md` | `docs/README.md`, package READMEs |
| Backend architecture and operations | `docs/backend_index.md`, `backend/docs/*.md` | `backend/README.md`, `docs/development.md` |
| Frontend architecture and operations | `docs/frontend_index.md`, `frontend/docs/*.md` | `frontend/README.md`, `docs/development.md` |
| iOS client behavior | `docs/ios_index.md`, `ios/docs/*.md` | `ios/README.md`, `docs/development.md` |
| Telegram transport behavior | `docs/telegram_index.md`, `telegram/docs/*.md` | `telegram/README.md`, `docs/development.md` |
| API contract | `docs/api.md`, `docs/api/*.md` | `docs/backend_index.md`, feature docs |
| Data schema and persistence | `docs/data-model.md` | `docs/backend_index.md`, ADRs |
| Feature deep dives | `docs/features/*.md` | `docs/backend_index.md`, `docs/frontend_index.md` |
| Active implementation work | `tasks/*.md` | issue or thread context |
| Historical implementation context | `docs/completed_tasks/*.md` | ADRs, stable docs |
| Agent workflow, editing standards, and local skills | `AGENTS.md`, `skills/*.md` | `docs/development.md` |

If documents conflict, update the primary source first and trim stale secondary copies.

## Update Protocol

- API change: update the relevant `docs/api/*.md` files and keep `docs/api.md` current when route-family navigation changed.
- Schema or migration change: update `docs/data-model.md`, the relevant `backend/docs/*.md` files, and `docs/repository-structure.md` if file maps or migration lists changed.
- Backend behavior change: update the relevant `backend/docs/*.md` files and the relevant feature doc.
- Frontend behavior or UX change: update the relevant `frontend/docs/*.md` files and the relevant feature doc.
- Workflow, setup, or tooling change: update `README.md`, `docs/development.md`, and this file.
- For Python tooling, keep local-only developer packages in `dependency-groups.dev` and document the normal workflow with `uv sync` / `uv run ...`, not a published `dev` extra.
- Major design decision: add or update an ADR in `docs/adr/`.
- New docs or removed docs: update `docs/README.md`.

## Task Document Rules

- Use `tasks/*.md` for work in progress.
- Move finished task docs that are worth keeping to `docs/completed_tasks/`.
- Name task files `YYYY-MM-DD_slug.md`.
- Do not treat task docs as the source of truth for current behavior after the work lands.

## Drift Prevention

Run:

```bash
uv run python scripts/check_docs_sync.py
```

Current checks enforce:

- required doc and pointer files exist
- `tasks/` and `docs/completed_tasks/` exist and the old plan directories are gone
- the docs index points to subsystem topic maps, the doc-system guide, the task archive guide, feature maps, and the ADR index
- package README files point back to canonical subsystem docs
- subsystem index docs point to their focused topic maps
- stale removed terms are absent from live reference docs
- key docs reference the latest Alembic migration
