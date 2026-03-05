# Documentation System

This document defines how to keep docs fast to navigate and hard to drift.

## Goals

- One obvious source of truth per topic.
- Minimal duplication across docs.
- Fast onboarding for humans and coding agents.

## Source-of-Truth Matrix

| Topic | Primary Source | Secondary References |
| --- | --- | --- |
| API contract | `docs/api.md` | `README.md`, `docs/backend.md`, module READMEs |
| Data schema/model | `docs/data-model.md` | `docs/backend.md`, ADRs |
| Backend architecture/operations | `docs/backend.md` | `backend/README.md`, `docs/development.md` |
| Frontend architecture/operations | `docs/frontend.md` | `frontend/README.md`, `docs/development.md` |
| Project setup/run | `README.md` | `docs/development.md` |
| Feature deep dives | `docs/feature-*.md` | `docs/backend.md`, `docs/frontend.md` |
| Structural decisions | `docs/adr/*.md` | `docs/architecture.md` |

Rule: if details conflict, update the primary source first.

## Todo/Completed Doc Naming

Files in `docs/todo/` and `docs/completed/` must use a date prefix (YYYY-MM-DD). Name new docs `YYYY-MM-DD_slug.md` (e.g. `2026-03-05_feature_proposal.md`).

## When To Update Which Docs

- API shape change: update `docs/api.md` + affected feature map + README summary.
- Schema/migration change: update `docs/data-model.md` + `docs/backend.md` + migration list references.
- UI behavior change: update `docs/frontend.md` + feature map.
- Operational command change: update `README.md` + `docs/development.md`.
- Major design decision: add an ADR in `docs/adr/`.

## Drift Prevention

Run:

```bash
uv run python scripts/check_docs_sync.py
```

Current checks:

- required doc/module README files exist
- latest Alembic migration is referenced in key docs
- stale known-removed terms are absent from live docs
- docs index references feature maps, ADR index, and doc-system guide

## PR Checklist (Docs)

1. Updated primary source-of-truth doc(s) for changed behavior.
2. Updated at least one feature map if user-facing behavior changed.
3. Added/updated ADR for major design decisions.
4. Ran docs check script locally.
