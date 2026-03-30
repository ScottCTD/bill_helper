# Backend Documentation

This file is the backend index. Use it to find the focused backend docs under `../backend/docs/`.

## Backend Doc Map

- `../backend/README.md`: local package navigation and change checklist.
- `../backend/docs/README.md`: topic map and fastest path to the right backend doc.
- `../backend/docs/runtime_and_config.md`: runtime entrypoints, configuration, and database bootstrap.
- `../backend/docs/domain_and_http.md`: models, schemas, core services, router boundaries, and non-agent HTTP behavior.
- `../backend/docs/agent_subsystem.md`: agent runtime, tools, review flow, and agent API ownership.
- `../backend/docs/operations.md`: migrations, test coverage, operational impact, and current constraints.

## Stable Boundaries

- Routers own HTTP translation and principal-boundary enforcement.
- `backend/auth/*` owns request-principal normalization plus FastAPI auth dependencies.
- `backend/routers/auth.py` and `backend/routers/admin.py` own session-auth and admin management HTTP routes.
- Services own domain policy, principal-scoped queries, and orchestration.
- The agent subsystem lives under `backend/services/agent/*` with `backend/routers/agent.py` as a thin transport aggregator over the split `agent_threads.py`, `agent_runs.py`, `agent_reviews.py`, and `agent_attachments.py` modules.
- Shared persistence and runtime configuration are centralized in `backend/database.py`, `backend/services/runtime_settings.py`, `backend/services/user_files.py`, and `backend/services/agent_workspace.py`.
- current-user workspace snapshot reads and file-tree shaping live in `backend/services/workspace_browser.py` with `backend/routers/workspace.py` as the HTTP boundary.

## Current Migration Head

- `0027_add_agent_bulk_concurrency_setting`
- `0028_add_available_agent_models_to_runtime_settings`
- `0029_add_agent_run_surface`
- `0030_add_account_agent_change_types`
- `0031_add_user_is_admin`
- `0032_add_filter_groups`
- `0033_multi_user_security`
- `0034_add_entry_tagging_model_to_runtime_settings`
- `0035_add_user_files_and_agent_workspace`
- `0036_add_agent_run_created_at_index`
- `0037_add_agent_message_attachments_use_ocr`

## Related Docs

- `docs/api.md`
- `docs/data_model.md`
- `docs/repository_structure.md`
