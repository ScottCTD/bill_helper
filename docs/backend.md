# Backend Documentation

This file is the backend index. Use it to find the focused backend docs under `docs/backend/`.

## Backend Doc Map

- `backend/README.md`: topic map and fastest path to the right backend doc.
- `backend/runtime-and-config.md`: runtime entrypoints, configuration, and database bootstrap.
- `backend/domain-and-http.md`: models, schemas, core services, router boundaries, and non-agent HTTP behavior.
- `backend/agent-subsystem.md`: agent runtime, tools, review flow, and agent API ownership.
- `backend/operations.md`: migrations, test coverage, operational impact, and current constraints.

## Stable Boundaries

- Routers own HTTP translation and principal-boundary enforcement.
- Services own domain policy and orchestration.
- The agent subsystem lives under `backend/services/agent/*` with `backend/routers/agent.py` as the transport layer.
- Shared persistence and runtime configuration are centralized in `backend/database.py` and `backend/services/runtime_settings.py`.

## Current Migration Head

- `0024_entity_root_accounts`

## Related Docs

- `docs/api.md`
- `docs/data-model.md`
- `docs/repository-structure.md`
