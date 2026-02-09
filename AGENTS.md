# AGENTS.md

## Project Agent Rules

These rules apply to any coding agent working in this repository.

## Python Tooling

For any Python-related work in this repository, use `uv` by default.

- Use `uv` to manage dependencies and environments.
- Use `uv run` to execute Python commands, scripts, tests, and tools.
- Prefer `uv` workflows over `pip`, `python -m venv`, or direct `python` execution unless explicitly required.

## Documentation Is Mandatory

When implementing any feature, bug fix, refactor, schema change, API change, build/tooling change, or behavior change, the agent must update documentation in the same work item.

Minimum required doc updates:

- `README.md` if setup, run commands, architecture summary, or project status changed.
- one or more files under `/docs` that describe the changed area.

If a change introduces a new subsystem/module/page/service, create a new documentation file under `/docs` when existing docs are insufficient.

## Documentation Quality Bar

Documentation updates must include:

- current behavior (not planned behavior)
- affected files/modules
- operational impact (commands, env vars, migrations, tests)
- constraints/known limitations where relevant

## Keep Docs and Code Synchronized

Do not leave docs stale after implementation.

If code and docs conflict, update docs before finishing.

## Documentation Synchronization Protocol (Required)

Treat docs as a maintained system, not ad-hoc notes.

When code changes, update the right source-of-truth docs in the same work item:

- API contract changes:
  - `/docs/api.md`
- Data model / migration / persistence changes:
  - `/docs/data-model.md`
  - `/docs/backend.md`
  - `/docs/repository-structure.md` (if file map or migration list changed)
- Backend behavior/flow changes:
  - `/backend/README.md`
  - `/docs/backend.md`
  - relevant feature map under `/docs/feature-*.md`
- Frontend behavior/UX changes:
  - `/frontend/README.md`
  - `/docs/frontend.md`
  - relevant feature map under `/docs/feature-*.md`
- Cross-cutting workflow/setup changes:
  - `/README.md`
  - `/docs/development.md`
  - `/docs/documentation-system.md` (if process/rules changed)
- Major architectural decisions:
  - add/update ADR under `/docs/adr/`

Also keep the docs index current when introducing new docs:

- `/docs/README.md`

### Required Verification Before Finishing

For any behavior/schema/API/tooling/UI change, run:

```bash
uv run python scripts/check_docs_sync.py
```

If it fails, fix docs before finalizing.

## Suggested Documentation Targets

- Architecture: `/docs/architecture.md`
- Repository map: `/docs/repository-structure.md`
- Backend details: `/docs/backend.md`
- Frontend details: `/docs/frontend.md`
- API contract: `/docs/api.md`
- Data model: `/docs/data-model.md`
- Dev workflow: `/docs/development.md`

## Commit Messages

When asked to write a commit message for the current changes, use this format:

- first line: overall change in imperative mood
- following lines: bullet points summarizing other changes
- do not invent details; only include what exists in the diff

## Skills

### Available skills

- notion-grade-ui: Enforces a calm, content-first, Notion-like frontend system with tokenized styling, primitives-first implementation, subtle interactions, and accessibility checks. Use for any UI/page/component/layout/control changes in `frontend`. (file: `/path/to/bill_helper/skills/notion-grade-ui/SKILL.md`)

### How to use skills

- Trigger the `notion-grade-ui` skill for frontend tasks that add or modify UI surface area.
- Skip this skill for pure backend-only changes or explicitly labeled design-system bypass experiments.
