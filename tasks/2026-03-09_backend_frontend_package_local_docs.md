# Backend And Frontend Package-Local Docs

## Status

Proposed.

## Question

Should this monorepo move backend and frontend subsystem docs out of the shared top-level `docs/` tree and into package-local folders such as `backend/docs/` and `frontend/docs/`, similar to `ios/docs/` and `telegram/docs/`?

## Current State

- `ios/` and `telegram/` already keep package-local docs.
- `backend/` and `frontend/` currently use thin local `README.md` files that point to canonical docs under `docs/backend/` and `docs/frontend/`.
- The docs system, docs index, and docs sync checker currently treat `docs/backend/*.md` and `docs/frontend/*.md` as the stable source of truth.

## Why This Refactor Might Help

- improve monorepo consistency across top-level packages
- keep docs physically closer to the code they describe
- make package ownership clearer when working inside `backend/` or `frontend/`
- reduce the split between package-local docs for some surfaces and centralized docs for others

## Risks And Open Questions

- avoid creating two competing documentation systems during migration
- decide whether `docs/backend.md` and `docs/frontend.md` remain top-level indexes or become simple pointers into package-local docs
- decide whether API docs stay centralized under `docs/api/` or move closer to backend docs
- update `scripts/check_docs_sync.py`, `docs/README.md`, `docs/documentation-system.md`, and `docs/repository-structure.md` together
- keep navigation simple for humans who start at the repo root

## Recommendation

This looks reasonable to explore. In a monorepo, package-local docs for `backend/` and `frontend/` would make the layout more consistent with `ios/` and `telegram/`.

The root `docs/` tree should remain the home for project-level and cross-cutting documentation, not component-owned implementation details.

The safest version is a staged migration:

1. Move focused backend docs from `docs/backend/*.md` to `backend/docs/*.md`.
2. Move focused frontend docs from `docs/frontend/*.md` to `frontend/docs/*.md`.
3. Keep top-level `docs/backend.md` and `docs/frontend.md` as cross-repo entry points that link into the package-local docs.
4. Keep cross-cutting docs such as `docs/architecture.md`, `docs/data-model.md`, and likely `docs/api/*.md` centralized unless there is a stronger ownership reason to move them later.

## Proposed End State

- `backend/docs/*.md`: backend subsystem source-of-truth docs
- `frontend/docs/*.md`: frontend subsystem source-of-truth docs
- `ios/docs/*.md`: unchanged
- `telegram/docs/*.md`: unchanged
- `docs/*.md`: project-level and cross-cutting docs such as architecture, development workflow, repository structure, ADRs, feature maps, and completed task archives
- `docs/backend.md` and `docs/frontend.md`: top-level indexes/pointers
- `docs/api/*.md`: centralized unless a later refactor decides otherwise

## Implementation Outline

1. Inventory all references to `docs/backend/` and `docs/frontend/`.
2. Create `backend/docs/README.md` and `frontend/docs/README.md`.
3. Move the focused subsystem docs while preserving filenames where practical.
4. Update top-level docs indexes and package-local READMEs.
5. Update `scripts/check_docs_sync.py` to validate the new paths.
6. Run docs sync and targeted navigation sanity checks.

## Exit Criteria

- backend and frontend follow the same package-local docs pattern already used by ios and telegram
- top-level docs remain easy to navigate from `README.md` and `docs/README.md`
- no duplicated canonical ownership between centralized and package-local docs
- `uv run python scripts/check_docs_sync.py` passes