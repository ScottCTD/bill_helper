# Backend Operations

## Migrations

- `0001_initial`
- `0002_entities_and_entry_entity_refs`
- `0003_entity_category`
- `0004_users_and_account_entity_links`
- `0005_remove_attachments`
- `0006_agent_append_only_core`
- `0007_taxonomy_core`
- `0008_agent_run_usage_metrics`
- `0009_remove_entry_status`
- `0010_runtime_settings_overrides`
- `0011_remove_openrouter_runtime_settings_fields`
- `0012_remove_related_link_type`
- `0013_add_account_markdown_body`
- `0014_remove_account_institution_type`
- `0015_add_agent_tool_call_output_text`
- `0016_add_user_memory_to_runtime_settings`
- `0017_rename_tag_category_taxonomy`
- `0018_add_tag_description`
- `0019_add_transfer_entry_kind`
- `0020_add_agent_message_attachment_original_filename`
- `0021_add_agent_run_context_tokens`
- `0022_agent_run_events_and_tool_lifecycle`
- `0023_add_agent_provider_config`
- `0024_entity_root_accounts`
- `0025_user_memory_json_list`
- `0026_entry_groups_v2`
- `0027_add_agent_bulk_concurrency_setting`
- `0028_add_available_agent_models_to_runtime_settings`
- `0029_add_agent_run_surface`
- `0030_add_account_agent_change_types`
- `0031_add_user_is_admin`
- `0032_add_filter_groups`
- `0033_multi_user_security`
- `0034_add_entry_tagging_model_to_runtime_settings`
- `0035_add_user_files_and_agent_workspace`

Commands:

- apply: `uv run alembic upgrade head`
- inspect state: `uv run alembic current`

## Bootstrap And Verification

Useful commands:

- bootstrap/reset admin: `uv run python scripts/bootstrap_admin.py --name <user> --password <pass>`
- build workspace image: `docker build -t bill-helper-agent-workspace:latest -f docker/agent-workspace.dockerfile .`
- py-compile touched modules: `uv run python -m py_compile ...`
- backend tests (fast default): `OPENROUTER_API_KEY=test uv run pytest backend/tests -q -m "not workspace_docker"`
- backend workspace tests (run when changing workspace lifecycle or IDE proxy behavior): `OPENROUTER_API_KEY=test uv run pytest backend/tests/test_agent_workspace.py -q -m workspace_docker`
- docs sync: `uv run python scripts/check_docs_sync.py`

## Operational Impact

- session auth stores only SHA-256 token digests in `sessions`
- deleting a user cascades through owned finance resources, agent threads, and sessions
- canonical user-visible files persist under `{data_dir}/user_files/{user_id}/uploads`
- agent message attachments are durable `user_files` rows linked from `agent_message_attachments`
- deleting a thread removes thread-scoped DB rows only; it no longer deletes uploaded payload files from disk
- admin bootstrap and user-create flows eagerly provision user file roots plus named Docker workspace resources when workspace provisioning is enabled
- user deletion removes the named workspace container, named workspace volume, and `{data_dir}/user_files/{user_id}`
- non-stream sends run in a background thread; stream sends emit SSE from the request and resume in background on disconnect if needed
- runtime settings are global to the app instance even though finance and agent resources are user-owned
- dashboard/filter-group reads lazily provision default filter groups per user
- taxonomy defaults (`entity_category`, `tag_type`) are auto-provisioned per user when missing

## Constraints And Known Limitations

- app auth is multi-user but still prototype-grade: there is one admin role and no finer-grained RBAC
- runtime settings remain global, not per user
- `agent_api_key` runtime overrides are stored as plaintext in the local DB for this prototype
- OCR fallback requires a local `tesseract` executable
- workspace provisioning requires a prebuilt local Docker image and host-daemon access; the backend does not build the image itself
- streaming uses SSE only; there is no websocket transport
- no autonomous or scheduled agent runs
- taxonomy assignments use string `subject_id` values without cross-table FK enforcement
- group nesting depth is limited to one and edges are derived only
