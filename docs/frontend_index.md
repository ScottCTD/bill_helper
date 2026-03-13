# Frontend Documentation

This file is the frontend index. Use it to find the focused frontend docs under `../frontend/docs/`.

## Frontend Doc Map

- `../frontend/README.md`: local package navigation and change checklist.
- `../frontend/docs/README.md`: topic map and fastest path to the right frontend doc.
- `../frontend/docs/app_shell_and_routing.md`: stack, runtime, app shell, and route layout.
- `../frontend/docs/client_and_state.md`: shared client layer, types, query keys, and invalidation.
- `../frontend/docs/workspaces.md`: page and workspace behavior outside the agent panel.
- `../frontend/docs/agent_workspace.md`: agent page, timeline, review modal, and composer behavior.
- `../frontend/docs/styles_and_operations.md`: shared components, styling system, operational impact, and constraints.

## Stable Boundaries

- Route pages stay thin composition shells.
- Feature-owned logic lives under `frontend/src/features/*`.
- Shared API contracts and query orchestration live under `frontend/src/lib/*`.
- The agent workspace lives under `frontend/src/features/agent/*`.

## Related Docs

- `docs/api.md`
- `docs/backend_index.md`
- `docs/features/account_reconciliation.md`
- `docs/features/dashboard_analytics.md`
