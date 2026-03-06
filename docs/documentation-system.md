# Documentation System

The docs in this repository are intentionally layered. Do not use one file for every audience.

## Layers

- `README.md`: onboarding, local setup, run commands, and top-level links.
- `AGENTS.md`: short working agreement for coding agents, including editing and refactor standards plus links to the right docs.
- `docs/*.md`: canonical human-facing index and reference docs for current behavior.
- `docs/backend/*.md`, `docs/frontend/*.md`, `docs/api/*.md`: focused subsystem docs owned under the canonical docs tree.
- `docs/exec-plans/active/*.md`: active implementation plans, migration notes, and temporary caveats.
- `docs/exec-plans/completed/*.md`: archived plans and retrospectives.
- `backend/README.md` and `frontend/README.md`: thin package-local pointer docs.
- Nested `AGENTS.md`: optional and path-scoped; only add when a subtree needs special editing rules.

## Boundary Rules

- System architecture belongs in `docs/architecture.md`, not in `AGENTS.md`.
- Filesystem mapping belongs in `docs/repository-structure.md`, not in package READMEs.
- Top-level subsystem files (`docs/backend.md`, `docs/frontend.md`, `docs/api.md`) are indexes, not dumping grounds.
- Stable backend behavior belongs in `docs/backend/*.md`.
- Stable frontend behavior belongs in `docs/frontend/*.md`.
- API contracts belong in `docs/api/*.md`.
- Temporary work notes, migration checklists, and refactor sequencing belong in `docs/exec-plans/`.
- Package READMEs should help local navigation and point to canonical docs. They should not grow into parallel architecture docs.

## Source-of-Truth Matrix

| Topic | Primary Source | Secondary References |
| --- | --- | --- |
| Project setup and dev loop | `README.md` | `docs/development.md` |
| Documentation policy | `docs/documentation-system.md` | `AGENTS.md`, `docs/README.md` |
| System architecture | `docs/architecture.md` | ADRs, `docs/backend.md`, `docs/frontend.md` |
| Repository layout | `docs/repository-structure.md` | `docs/README.md`, package READMEs |
| Backend architecture and operations | `docs/backend.md`, `docs/backend/*.md` | `backend/README.md`, `docs/development.md` |
| Frontend architecture and operations | `docs/frontend.md`, `docs/frontend/*.md` | `frontend/README.md`, `docs/development.md` |
| API contract | `docs/api.md`, `docs/api/*.md` | `docs/backend.md`, feature docs |
| Data schema and persistence | `docs/data-model.md` | `docs/backend.md`, ADRs |
| Feature deep dives | `docs/feature-*.md` | `docs/backend.md`, `docs/frontend.md` |
| Active implementation work | `docs/exec-plans/active/*.md` | issue or thread context |
| Historical implementation context | `docs/exec-plans/completed/*.md` | ADRs, stable docs |
| Agent workflow, editing standards, and local skills | `AGENTS.md`, `skills/*.md` | `docs/development.md` |

If documents conflict, update the primary source first and trim stale secondary copies.

## Update Protocol

- API change: update the relevant `docs/api/*.md` files and keep `docs/api.md` current when route-family navigation changed.
- Schema or migration change: update `docs/data-model.md`, the relevant `docs/backend/*.md` files, and `docs/repository-structure.md` if file maps or migration lists changed.
- Backend behavior change: update the relevant `docs/backend/*.md` files and the relevant feature doc.
- Frontend behavior or UX change: update the relevant `docs/frontend/*.md` files and the relevant feature doc.
- Workflow, setup, or tooling change: update `README.md`, `docs/development.md`, and this file.
- Major design decision: add or update an ADR in `docs/adr/`.
- New docs or removed docs: update `docs/README.md`.

## Execution Plan Rules

- Use `docs/exec-plans/active/` for work in progress.
- Use `docs/exec-plans/completed/` for finished plans and retrospectives.
- Name execution-plan files `YYYY-MM-DD_slug.md`.
- Do not treat execution plans as the source of truth for current behavior after the work lands.

## Drift Prevention

Run:

```bash
uv run python scripts/check_docs_sync.py
```

Current checks enforce:

- required doc and pointer files exist
- `docs/exec-plans/` exists and the old plan directories are gone
- the docs index points to subsystem topic maps, the doc-system guide, the execution-plan guide, feature maps, and the ADR index
- package README files point back to canonical subsystem docs
- subsystem index docs point to their focused topic maps
- stale removed terms are absent from live reference docs
- key docs reference the latest Alembic migration
