# AGENTS.md

These rules apply to any coding agent working in this repository.

## Working Style

- This project is a prototype. Prefer simplification and replacement over compatibility shims.
- Use `uv` for Python dependency management, scripts, tests, and tooling.
- Keep docs synchronized with code changes in the same work item.

## Architecture Standards

### Ownership Boundaries

- Routers own HTTP translation only: request parsing, response mapping, and status codes.
- Services own domain policy and orchestration.
- Storage and file lifecycle logic belongs in dedicated service modules, not routers.
- Tool interfaces should stay thin: registries plus focused handlers, not monolithic switch modules.

### Module Decomposition

- Split mixed-responsibility modules into focused modules.
- Add a subpackage only when multiple durable siblings justify the extra depth.
- Avoid singleton subpackages when a direct module path is clearer.
- Keep one coordinator per execution mode and move persistence or event helpers into support modules.
- Promote shared helpers into one canonical module instead of duplicating them across layers.

### Errors and Fallbacks

- Do not use silent broad `except Exception` handlers without contextual logging.
- Recoverable fallbacks must emit scope and context metadata.
- CLI entrypoints should return status codes from `main()`; business logic should raise exceptions.

### Testability and Refactors

- Tests should target stable service seams, not router-private helpers.
- Keep monkeypatch points on public or otherwise stable callsites.
- For architectural refactors, run targeted tests plus the full backend suite.
- Use this refactor playbook: capture the finding and root cause, move ownership to the correct layer, keep compatibility seams only when they are still needed, update docs in the same work item, and rerun the verification gates.
- For explicit desloppify campaigns, record durable fix batches in a dated fix-log doc under `docs/completed_tasks/`.

### Architecture Verification Gates

- `uv run python -m py_compile ...` on touched Python modules
- `OPENROUTER_API_KEY=test uv run pytest backend/tests -q`
- `uv run python scripts/check_docs_sync.py`

## Documentation

### System

- `README.md`: onboarding, setup, dev loop, and links only.
- `docs/README.md`: canonical index into the human-facing docs tree.
- `docs/*.md`: stable index docs and cross-cutting reference docs.
- `backend/docs/*.md`, `frontend/docs/*.md`, `ios/docs/*.md`, `telegram/docs/*.md`, and `docs/api/*.md`: focused subsystem source-of-truth docs.
- `tasks/*.md`: active implementation plans, temporary caveats, and migration checklists.
- `docs/completed_tasks/*.md`: completed plans and retrospectives kept for history.
- `backend/README.md` and `frontend/README.md`: thin local navigation docs that point to the package-local canonical docs plus the top-level indexes.
- Add nested `AGENTS.md` files only when a subtree has genuinely different editing rules. Do not use nested agent files as architecture docs.

### Required Doc Updates

- API contract changes: update the relevant `/docs/api/*.md` files and keep `/docs/api.md` current when the route-family map changes.
- Data model or migration changes: update `/docs/data-model.md`, `/docs/backend_index.md`, the relevant `/backend/docs/*.md` files, and `/docs/repository-structure.md` when file maps or migration lists changed.
- Backend behavior changes: update the relevant `/backend/docs/*.md` files and any affected `/docs/features/*.md`.
- Frontend behavior changes: update the relevant `/frontend/docs/*.md` files and any affected `/docs/features/*.md`.
- Cross-cutting workflow or tooling changes: update `/README.md`, `/docs/development.md`, and `/docs/documentation-system.md`.
- Major architectural decisions: add or update an ADR under `/docs/adr/`.
- When introducing or removing docs, keep `/docs/README.md` current.

### Quality Bar

- Document current behavior, not planned behavior.
- Include affected files or modules, operational impact, and constraints where relevant.
- Stable docs explain how the system works now.
- Temporary implementation notes belong in `tasks/`, not in stable reference pages.

### Required Verification

For any behavior, schema, API, tooling, or UI change, run:

```bash
uv run python scripts/check_docs_sync.py
```

If it fails, fix the docs before finishing.

### Feature Requests from Active Tasks

When the user requests a feature from `tasks/*.md`, ask whether to move that task doc to `docs/completed_tasks/` after implementation.

## Before Committing

- Review `git diff` for secrets, tokens, credentials, local paths, financial data, or other sensitive material.
- Do not commit until the diff is clean.

## Commit Messages

- First line: overall change in imperative mood.
- Following lines: bullet points summarizing concrete changes in the diff.
- Do not invent details.

## Repo-Local Skills

- `notion-grade-ui`: use for frontend UI work in `frontend/`.
- `desloppify-maintenance`: use only for explicit desloppify or score-driven cleanup requests.
