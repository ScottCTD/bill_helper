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
- `backend/auth/*` owns request-principal normalization plus FastAPI auth dependencies.
- Services own domain policy, principal-scoped queries, and orchestration.
- The agent subsystem lives under `backend/services/agent/*` with `backend/routers/agent.py` as a thin transport aggregator over the split `agent_threads.py`, `agent_runs.py`, `agent_reviews.py`, and `agent_attachments.py` modules.
- Shared persistence and runtime configuration are centralized in `backend/database.py` and `backend/services/runtime_settings.py`.

## Current Migration Head

- `0026_entry_groups_v2`
- `0027_add_agent_bulk_concurrency_setting`
- `0028_add_available_agent_models_to_runtime_settings`
- `0029_add_agent_run_surface`
- `0030_add_account_agent_change_types`
- `0031_add_user_is_admin`

## Related Docs

- `docs/api.md`
- `docs/data-model.md`
- `docs/repository-structure.md`
