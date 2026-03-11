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

Commands:

- apply: `uv run alembic upgrade head`
- inspect state: `uv run alembic current`

## Testing

Key backend test modules:

- `backend/tests/test_entries.py`
- `backend/tests/test_finance.py`
- `backend/tests/test_agent.py`
- `backend/tests/test_agent_performance.py`
- `backend/tests/test_agent_model_client.py`
- `backend/tests/test_agent_pricing.py`
- `backend/tests/test_taxonomies.py`
- `backend/tests/test_settings.py`

Current baseline noted in docs: `backend/tests/test_agent.py` was at `76 passed` when this documentation was last expanded.

## Operational Impact

- agent uploads persist under `{data_dir}/agent_uploads`
- deleting a thread removes its attachment directories under `{data_dir}/agent_uploads/<message_id>/...`
- non-stream sends run in a background thread; stream sends emit SSE from the request and resume in background on disconnect if needed
- thread summaries include `has_running_run`
- runtime settings can change dashboard currency, default entry currency, and agent execution settings without restarting the app
- account IDs are shared entity-root IDs after `0024_entity_root_accounts`
- groups are first-class records after `0026_entry_groups_v2`; topology is derived from direct membership plus `group_type`
- deleting an account removes its snapshots, preserves denormalized entry labels, and clears linked account or entity FKs
- dashboard analytics exclude internal transfers when both endpoints resolve to account-backed entity roots
- dashboard analytics now provision and persist per-user default filter groups on first dashboard/filter-group read
- taxonomy defaults (`entity_category`, `tag_type`) are auto-provisioned by service logic when missing

## Constraints And Known Limitations

- no auth or permissions beyond the current prototype principal model
- runtime settings are global to the app instance, not per authenticated user
- runtime `agent_api_key` overrides are stored as plaintext in the local DB for this prototype
- OCR fallback requires a local `tesseract` executable
- streaming uses SSE only; there is no websocket transport
- no autonomous or scheduled agent runs
- taxonomy assignment storage uses string `subject_id` values without cross-table FK enforcement
- group nesting depth is limited to one and edges are derived only; there is no explicit edge editing surface
- filter-group logic currently supports `entry_kind`, tag inclusion/exclusion, and `is_internal_transfer`; richer fields need additional rule operators
