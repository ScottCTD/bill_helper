# Frontend Documentation

This file is the frontend index. Use it to find the focused frontend docs under `docs/frontend/`.

## Frontend Doc Map

- `frontend/README.md`: topic map and fastest path to the right frontend doc.
- `frontend/app-shell-and-routing.md`: stack, runtime, app shell, and route layout.
- `frontend/client-and-state.md`: shared client layer, types, query keys, and invalidation.
- `frontend/workspaces.md`: page and workspace behavior outside the agent panel.
- `frontend/agent-workspace.md`: agent page, timeline, review modal, and composer behavior.
- `frontend/styles-and-operations.md`: shared components, styling system, operational impact, and constraints.

## Stable Boundaries

- Route pages stay thin composition shells.
- Feature-owned logic lives under `frontend/src/features/*`.
- Shared API contracts and query orchestration live under `frontend/src/lib/*`.
- The agent workspace lives under `frontend/src/features/agent/*`.

## Related Docs

- `docs/api.md`
- `docs/backend.md`
- `docs/feature-account-reconciliation.md`
- `docs/feature-dashboard-analytics.md`
