# Repository Structure (Current)

## Root

- `.gitignore`: ignores venv, build outputs, runtime data, test cache.
- `.env.example`: env-var template with all supported variables (committed; no secrets).
- `.python-version`: local Python version hint.
- `README.md`: top-level guide and quickstart.
- `AGENTS.md`: project-wide coding-agent rules and doc-update requirements.
- `pyproject.toml`: Python package metadata, dependencies, scripts, pytest config.
- `uv.lock`: locked Python dependency graph for `uv`.
- `main.py`: thin launcher delegating to backend app entrypoint.
- `alembic.ini`: Alembic runtime/logging configuration.
- `.github/workflows/docs-consistency.yml`: CI docs drift checks.

## Migration Layer (`/alembic`)

- `env.py`: Alembic environment setup and metadata wiring.
- `script.py.mako`: migration template.
- `versions/0001_initial.py`: baseline schema migration.
- `versions/0002_entities_and_entry_entity_refs.py`: entity table + entry entity reference migration.
- `versions/0003_entity_category.py`: entity category column migration.
- `versions/0004_users_and_account_entity_links.py`: users table, account<->entity link, and entry owner->user migration.
- `versions/0005_remove_attachments.py`: removes legacy attachment table/endpoints.
- `versions/0006_agent_append_only_core.py`: introduces agent thread/run/tool-call/change-item/review tables.
- `versions/0007_taxonomy_core.py`: introduces taxonomy/taxonomy_terms/taxonomy_assignments and backfills entity categories.
- `versions/0008_agent_run_usage_metrics.py`: adds run usage token columns.
- `versions/0009_remove_entry_status.py`: drops the obsolete entry `status` column.
- `versions/0010_runtime_settings_overrides.py`: adds persisted runtime settings override table (`runtime_settings`).
- `versions/0011_remove_openrouter_runtime_settings_fields.py`: removes legacy OpenRouter-specific runtime settings columns.
- `versions/0012_remove_related_link_type.py`: migrates legacy `RELATED` entry links to `BUNDLE` and removes `RELATED` from `LinkType`.
- `versions/0013_add_account_markdown_body.py`: adds optional account-level markdown notes (`accounts.markdown_body`).
- `versions/0014_remove_account_institution_type.py`: drops legacy account columns (`accounts.institution`, `accounts.account_type`).
- `versions/0015_add_agent_tool_call_output_text.py`: adds persisted model-visible tool output text (`agent_tool_calls.output_text`).
- `versions/0016_add_user_memory_to_runtime_settings.py`: adds optional persistent agent memory text to runtime settings (`runtime_settings.user_memory`).
- `versions/0017_rename_tag_category_taxonomy.py`: migrates tag taxonomy key/display naming from category to type (`tag_category` -> `tag_type`).
- `versions/0018_add_tag_description.py`: adds optional free-text tag description (`tags.description`).
- `versions/0019_add_transfer_entry_kind.py`: documents addition of `TRANSFER` to `EntryKind` enum (no DDL change for SQLite).
- `versions/0020_add_agent_message_attachment_original_filename.py`: adds optional upload-name storage for agent attachments (`agent_message_attachments.original_filename`) and safely no-ops if the column already exists in a drifted local DB.
- `versions/0021_add_agent_run_context_tokens.py`: adds nullable prompt-size snapshots for agent runs (`agent_runs.context_tokens`) and safely no-ops if the column already exists.
- `versions/0022_agent_run_events_and_tool_lifecycle.py`: adds persisted run-event timeline rows (`agent_run_events`) and expands `agent_tool_calls` with lifecycle metadata (`llm_tool_call_id`, `started_at`, `completed_at`, queued/running/cancelled states).
- `versions/0023_add_agent_provider_config.py`: adds custom provider configuration fields to runtime settings (`agent_base_url`, `agent_api_key`).
- `versions/__init__.py`: package marker.

## Backend (`/backend`)

- `__init__.py`: package marker.
- `config.py`: settings model and environment variable binding.
- `database.py`: SQLAlchemy engine/session setup.
- `enums.py`: domain enums (`EntryKind`, `LinkType`, agent enums).
- `models.py`: SQLAlchemy ORM models.
- `schemas.py`: Pydantic request/response schemas.
- `main.py`: FastAPI app creation, routing, CORS, health check.
- `README.md`: backend-local change map and operational commands.

### Backend Routers (`/backend/routers`)

- `accounts.py`: accounts, snapshots, reconciliation endpoints.
- `users.py`: system-level user list/create/update endpoints.
- `entries.py`: entry CRUD, filtering, link creation.
- `entities.py`: entity list/create/update endpoints for entry selectors/properties.
- `tags.py`: tag list/create/update endpoints for property/tag selectors.
- `taxonomies.py`: taxonomy/term list and term create/rename endpoints.
- `currencies.py`: currency catalog placeholder endpoint for selector/property tables.
- `links.py`: link deletion endpoint.
- `groups.py`: derived entry-group read models (`GET /groups` summary + `GET /groups/{id}` graph).
- `dashboard.py`: monthly analytics endpoint.
- `agent.py`: append-only agent thread/message/run/review endpoints.
- `settings.py`: runtime settings read/update endpoints for user overrides with env fallback where applicable and DB-backed `user_memory`.

### Backend Services (`/backend/services`)

- `entries.py`: tag handling and entry soft-delete helper.
- `tags.py`: tag color helpers (normalization and random default color generation).
- `entities.py`: entity normalization and lookup helpers.
- `users.py`: user normalization, lookup, and current-user helpers.
- `groups.py`: connected-component recomputation for `group_id`.
- `finance.py`: reconciliation, CAD dashboard analytics, projections, and chart-ready breakdown aggregations.
- `serializers.py`: ORM-to-schema mapping helpers.
- `taxonomy.py`: shared taxonomy normalization, term assignment, and usage-count helpers.
- `runtime_settings.py`: resolves effective runtime settings from persisted overrides + env defaults, plus DB-backed `user_memory`.
- `agent/`: agent runtime, tool execution, prompt-size counting, serialization, prompt/model adapters, and review apply handlers.

### Backend Tests (`/backend/tests`)

- `conftest.py`: test app/client setup with isolated SQLite DB.
- `test_entries.py`: entry/link/group/delete behavior tests.
- `test_finance.py`: reconciliation and dashboard aggregation tests.
- `test_taxonomies.py`: taxonomy endpoints and tag/entity category assignment behavior tests.

## Frontend (`/frontend`)

- `package.json`: npm scripts and frontend dependencies.
- `package-lock.json`: locked npm dependencies.
- `vite.config.ts`: dev server config and API proxy.
- `vitest.config.ts`: frontend unit test runner configuration (`jsdom` + RTL setup).
- `tsconfig.json`: TypeScript compiler settings.
- `index.html`: Vite app shell.
- `README.md`: frontend-local change map and UI workflow notes.

### Frontend Source (`/frontend/src`)

- `main.tsx`: React root and providers.
- `App.tsx`: top-level shell layout (sidebar + content) and route map.
- `styles.css`: global styling including sidebar and app-shell classes.
- `test/`: frontend test setup, typed fixture factories, and shared query-client test renderer.

#### Components (`/frontend/src/components`)

- `Sidebar.tsx`: collapsible left-panel navigation with icon+label links.
- `MetricCard.tsx`: reusable metric container.
- `LineChart.tsx`: legacy SVG daily expense chart helper (dashboard now uses Recharts).
- `GroupGraphView.tsx`: React Flow-based graph rendering for entry groups.
- `TagMultiSelect.tsx`: Notion-style chip/dropdown multi-select for entry tags.
- `EntryEditorModal.tsx`: shared popup for entry create/edit.
- `MarkdownBlockEditor.tsx`: BlockNote wrapper for markdown + pasted images.
- `agent/AgentRunBlock.tsx`: extracted run activity/summary renderer used by `AgentPanel`.
- `agent/activity.ts`: extracted run/activity derivation helpers for agent timeline state.
- `agent/panel/*`: agent panel presentation layer (`AgentThreadList`, `AgentThreadPanel`, `AgentTimeline`, `AgentComposer`, `AgentThreadUsageBar`, `AgentAttachmentPreviewDialog`) plus panel-local hooks (`useResizablePanel`, `useStickToBottom`, `useAgentDraftAttachments`), type and format helpers.

#### Pages (`/frontend/src/pages`)

- `DashboardPage.tsx`: tabbed interactive analytics dashboard (overview/daily/breakdowns/insights) backed by Recharts.
- `SettingsPage.tsx`: responsive runtime settings workspace (general, persistent agent memory, agent runtime, reliability).
- `EntriesPage.tsx`: list/filter/delete entries and open popup create/edit editor.
- `EntryDetailPage.tsx`: manage links/group graph and open popup editor for updates.
- `GroupsPage.tsx`: derived group workspace (group list, graph detail, and link-driven topology edits).
- `AccountsPage.tsx`: thin page orchestrator that composes accounts feature modules.
- `PropertiesPage.tsx`: thin page orchestrator that composes properties feature modules.
- `AccountsPage.test.tsx`: page-level integration tests for account create/snapshot flows.
- `PropertiesPage.test.tsx`: page-level integration tests for users/taxonomy flows.

#### Feature Modules (`/frontend/src/features`)

- `accounts/`
  - `useAccountsPageModel.ts`: query/mutation orchestration, derived state, and action handlers.
  - `AccountsTableSection.tsx`: account table/search/selection UI.
  - `ReconciliationSection.tsx`: account reconciliation summary UI.
  - `SnapshotsSection.tsx`: snapshot create/history UI.
  - `AccountDialogs.tsx`: create/edit account dialog UI.
  - `helpers.ts`, `types.ts`: normalization helpers and local state contracts.
- `properties/`
  - `usePropertiesPageModel.ts`: top-level properties coordinator composing query/state/mutation hooks.
  - `usePropertiesQueries.ts`: users/entities/tags/currencies/taxonomy queries + derived option/label state.
  - `usePropertiesSectionState.ts`: section routing/search/create-panel state.
  - `usePropertiesFormState.ts`: section form/editing state.
  - `usePropertiesFilteredData.ts`: filtered list derivation by section search state.
  - `sections/*.tsx`: dedicated users/entities/tags/currencies/taxonomy section UI blocks.
  - `helpers.ts`, `types.ts`: filtering/taxonomy helpers and section contracts.

#### Frontend Lib (`/frontend/src/lib`)

- `types.ts`: shared TS API/data types.
- `api.ts`: fetch wrappers and API request functions.
- `format.ts`: money formatting and date helpers.
- `queryKeys.ts`: centralized TanStack Query key factory for all domains.
- `queryInvalidation.ts`: shared cache invalidation rules after mutations/review actions.

## Supporting Directories

- `/docs`: architecture and engineering documentation.
  - `documentation-system.md`: source-of-truth matrix + anti-drift workflow.
  - `feature-entry-lifecycle.md`: entry-domain flow map.
  - `feature-dashboard-analytics.md`: dashboard flow map.
  - `feature-account-reconciliation.md`: account workspace + snapshot/reconciliation flow map.
  - `/adr`: architecture decision records.
- `/skills/notion-grade-ui/SKILL.md`: project-local frontend UI quality skill for calm, tokenized, primitives-first design implementation.
- `/scripts/seed_defaults.py`: reset local DB and seed default tags, entity categories, and accounts.
- `/scripts/seed_demo.py`: local seed dataset generation.
- `/scripts/setup_shared_env.sh`: copies `.env` (or `.env.example`) to `~/.config/bill-helper/.env` for cross-worktree secret sharing.
- `/scripts/check_docs_sync.py`: docs consistency checks (migration refs + stale term detection + index links).
- `/.data` (runtime, legacy): per-worktree SQLite DB override location (ignored in git). Default data location is `~/.local/share/bill-helper/`.

## Benchmark (`/benchmark`)

Agent import benchmark framework for evaluating LLMs on bank-statement-to-entry extraction.

- `snapshot.py`: create/restore/list DB snapshots.
- `create_empty_snapshot.py`: create default snapshot with accounts, tags, entity categories.
- `runner.py`: run benchmark cases against a model (parallel via `ProcessPoolExecutor`).
- `scorer.py`: match predicted entries to ground truth, compute field-level and aggregate scores, compare models.
- `generate_ground_truth.py`: run a capable model to produce draft ground truth for manual editing.
- `schemas.py`: Pydantic schemas for case input, ground truth, and result data.
- `README.md`: benchmark usage guide.
- `fixtures/` (gitignored): DB snapshots and benchmark cases (private data).
- `results/` (gitignored): run outputs, interaction traces, per-case scores (private).
- `reports/` (tracked): aggregate metrics and comparison reports (public).
