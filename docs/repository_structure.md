# Repository Structure (Current)

## Root

- `.gitignore`: ignores venv, build outputs, runtime data, test cache.
- `.env.example`: env-var template with all supported variables (committed; no secrets).
- `.python-version`: local Python version hint.
- `README.md`: top-level onboarding, setup, and dev loop.
- `AGENTS.md`: short coding-agent working agreement plus links to canonical docs.
- `pyproject.toml`: Python package metadata, dependencies, scripts, pytest config.
- `uv.lock`: locked Python dependency graph for `uv`.
- `alembic.ini`: Alembic runtime/logging configuration.
- `docker/`: Dockerfiles for local sandbox/runtime images, including the agent workspace image.
- `ios/`: SwiftUI iOS MVP workspace containing the app shell target, shared mobile core sources, feature surfaces, `ios/docs/` client notes, and focused API/unit tests.
- `telegram/`: top-level Telegram transport package with `telegram/README.md`, `telegram/docs/` implementation notes, config, PTB application/handler wiring, the `telegram/ptb.py` import-collision shim/re-export for `python-telegram-bot`, polling/webhook intake adapters, file/reply helpers, and targeted tests for the bot integration surface.

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
- `versions/0016_add_user_memory_to_runtime_settings.py`: adds optional persistent agent memory storage to runtime settings (`runtime_settings.user_memory`).
- `versions/0017_rename_tag_category_taxonomy.py`: migrates tag taxonomy key/display naming from category to type (`tag_category` -> `tag_type`).
- `versions/0018_add_tag_description.py`: adds optional free-text tag description (`tags.description`).
- `versions/0019_add_transfer_entry_kind.py`: documents addition of `TRANSFER` to `EntryKind` enum (no DDL change for SQLite).
- `versions/0020_add_agent_message_attachment_original_filename.py`: adds optional upload-name storage for agent attachments (`agent_message_attachments.original_filename`) and safely no-ops if the column already exists in a drifted local DB.
- `versions/0021_add_agent_run_context_tokens.py`: adds nullable prompt-size snapshots for agent runs (`agent_runs.context_tokens`) and safely no-ops if the column already exists.
- `versions/0022_agent_run_events_and_tool_lifecycle.py`: adds persisted run-event timeline rows (`agent_run_events`) and expands `agent_tool_calls` with lifecycle metadata (`llm_tool_call_id`, `started_at`, `completed_at`, queued/running/cancelled states).
- `versions/0023_add_agent_provider_config.py`: adds custom provider configuration fields to runtime settings (`agent_base_url`, `agent_api_key`).
- `versions/0024_entity_root_accounts.py`: rebuilds accounts as entity-root records by rekeying `accounts.id` to shared `entities.id` values and updating dependent account references.
- `versions/0025_user_memory_json_list.py`: normalizes persisted runtime user memory into JSON list form for prompt rendering and add-only appends.
- `versions/0026_entry_groups_v2.py`: replaces link-derived groups with first-class typed groups and membership rows, migrates compatible legacy linked components, and removes `entries.group_id` plus `entry_links`.
- `versions/0027_add_agent_bulk_concurrency_setting.py`: adds persisted Bulk mode concurrency control to runtime settings (`agent_bulk_max_concurrent_threads`).
- `versions/0028_add_available_agent_models_to_runtime_settings.py`: adds persisted ordered runtime model-list overrides (`runtime_settings.available_agent_models`).
- `versions/0029_add_agent_run_surface.py`: adds persisted run surface hints for Telegram-aware agent execution and reply reads.
- `versions/0030_add_account_agent_change_types.py`: expands the agent review enum to persist account create/update/delete proposal types.
- `versions/0031_add_user_is_admin.py`: adds the persisted `users.is_admin` role gate used by principal resolution and admin-only route checks.
- `versions/0032_add_filter_groups.py`: adds principal-owned saved filter-group definitions for dashboard classification and analytics slices.
- `versions/0033_multi_user_security.py`: adds password hashes and sessions, makes owned resources explicitly user-scoped, and migrates user deletion to cascade semantics.
- `versions/0034_add_entry_tagging_model_to_runtime_settings.py`: adds the optional runtime override for inline AI entry tag suggestions (`runtime_settings.entry_tagging_model`).
- `versions/0035_add_user_files_and_agent_workspace.py`: adds the canonical `user_files` registry, rewires historical agent attachments to it, and introduces per-user workspace provisioning support.
- `versions/__init__.py`: package marker.

## Backend (`/backend`)

- `__init__.py`: package marker.
- `config.py`: settings model and environment variable binding.
- `__main__.py`: package-local launcher (`python -m backend`).
- `db_meta.py`: side-effect-free SQLAlchemy metadata root (`Base`).
- `database.py`: explicit SQLAlchemy engine/session factories plus cached runtime accessors/dependencies.
- `enums_finance.py`: ledger enums (`EntryKind`, `GroupType`, `GroupMemberRole`, plus legacy migration-only `LinkType`).
- `enums_agent.py`: agent run/review/message enums.
- `models_finance.py`: ledger/account/entity/tag/taxonomy/filter-group/entry ORM models.
- `models_agent.py`: agent thread/run/tool-call/change/review ORM models.
- `models_files.py`: canonical per-user durable file registry ORM model.
- `models_settings.py`: runtime settings ORM model and table mapping.
- `contracts_groups.py`: shared group create/update contracts and the typed group-member target payload used by schemas, routers, services, and group-member apply flows.
- `contracts_users.py`: shared user create/update contracts reused by schemas, routers, and services.
- `contracts_settings.py`: shared runtime-settings write contract used by both schema and service layers.
- `models_shared.py`: shared model defaults (`utc_now`, `uuid_str`) used by both model domains.
- `schemas_finance.py`: ledger, filter-group, and dashboard request/response schemas.
- `schemas_agent.py`: agent thread/message/run/review request/response schemas.
- `schemas_auth.py`: auth, admin-user, and admin-session request/response schemas.
- `schemas_settings.py`: runtime settings request/response schemas.
- `schemas_workspace.py`: current-user workspace snapshot and recursive file-tree schemas.
- `auth/`: request-principal contracts, explicit dev-session header parsing, and FastAPI auth dependencies.
- `validation/`: neutral validation/normalization helpers plus shared contract field types used by schemas, services, and tool-input models.
- `main.py`: FastAPI app creation, routing, CORS, health check.
- `README.md`: thin backend-local navigation doc that points to canonical docs.
- `docs/`: package-local backend subsystem docs (`README.md`, `runtime_and_config.md`, `domain_and_http.md`, `agent_subsystem.md`, `operations.md`).

### Backend Routers (`/backend/routers`)

- `accounts.py`: accounts, account deletion, snapshots, reconciliation endpoints.
- `auth.py`: login/logout/current-session endpoints.
- `admin.py`: admin user/session management and impersonation endpoints.
- `users.py`: visible-user reads plus self-service password change.
- `entries.py`: entry CRUD, filtering, and direct group-context reads.
- `entities.py`: entity list/create/update/delete endpoints for entry selectors/properties.
- `tags.py`: tag list/create/update/delete endpoints for property/tag selectors.
- `taxonomies.py`: taxonomy/term list and term create/rename endpoints.
- `currencies.py`: currency catalog placeholder endpoint for selector/property tables.
- `groups.py`: first-class group CRUD, typed membership mutation, and derived direct-member graph reads.
- `filter_groups.py`: principal-owned saved filter-group CRUD for dashboard analytics classification.
- `dashboard.py`: monthly analytics endpoint.
- `agent.py`: append-only agent thread/message/run/review endpoints.
- `settings.py`: runtime settings read/update endpoints backed by `models_settings.py` / `schemas_settings.py`, with env fallback where applicable and DB-backed list-form `user_memory`.
- `workspace.py`: current-user workspace snapshot, explicit start/stop endpoints, IDE launch endpoint, and same-origin IDE proxy routes for the per-user sandbox.
- non-admin principal scope applies to owned-resource routes (`accounts`, `entries`, `users`, `groups`, `dashboard`).
- shared dictionary mutation routes (`entities`, `tags`, `taxonomies` POST/PATCH, plus entity and tag DELETE) require admin principal.

### Backend Services (`/backend/services`)

- `accounts.py`: account create/update/delete workflows for shared account/entity roots.
- `entries.py`: typed entry create/update workflows, typed entity/user refs, tag handling, and entry soft-delete helper.
- `filter_group_rules.py`: recursive rule evaluation and plain-language summaries for saved filter groups.
- `filter_groups.py`: default filter-group provisioning plus principal-scoped filter-group CRUD and rule persistence.
- `finance_contracts.py`: service-owned account/entity/tag write commands shared across routers and agent apply flows.
- `tags.py`: tag CRUD helpers, taxonomy cleanup, and random default color generation.
- `entities.py`: entity normalization, account-backed guards, and preserve-label delete helpers.
- `users.py`: user normalization, lookup, and current-user helpers.
- `principals.py`: request-principal materialization from a persisted user row plus optional session row.
- `passwords.py`: Argon2 hashing and reset-required password helpers.
- `sessions.py`: session creation, lookup, and revocation.
- `groups.py`: group CRUD, typed membership validation, depth-1 nesting enforcement, and derived graph generation.
- `finance.py`: reconciliation, runtime-currency dashboard analytics, filter-group-powered classification rollups, projections, and chart-ready breakdown aggregations.
- `crud_policy.py`: shared CRUD validation/conflict policy primitives and standardized error-translation helpers.
- `serializers.py`: ORM-to-schema mapping helpers.
- `taxonomy.py`: shared taxonomy normalization, term assignment, and usage-count helpers.
- `runtime_settings.py`: resolves effective runtime settings from persisted overrides + env defaults, including DB-backed ordered `user_memory` and `available_agent_models` support.
- `user_files.py`: canonical per-user file path management, atomic writes/imports, hashing, and artifact-promotion helpers.
- `user_file_workspace_view.py`: backend-managed read-only workspace mirror stored under each user's canonical file root and exposed inside the IDE as `/workspace/user_data`.
- `docker_cli.py`: thin Docker CLI adapter for image/volume/container lifecycle helpers.
- `agent_workspace.py`: deterministic per-user workspace spec construction plus Docker-backed provisioning/start-stop/remove helpers.
- `workspace_browser.py`: current-user workspace snapshot shaping for lifecycle and IDE launch state.
- `workspace_ide.py`: IDE launch-cookie helpers plus same-origin proxy header policy for `code-server`.
- `agent/`: agent runtime, tool execution, prompt-size counting, serialization, prompt/model adapters, and review apply handlers.
  - `tool_args/`: focused tool-input package for read filters, progress/session commands, thread rename, and pending-proposal admin wrappers.
  - `session_tools/`: session-scoped non-proposal tool handlers for progress updates, add-only memory appends, and thread rename operations.
  - `threads.py`: thread lookup and rename persistence helpers used by the router and tool runtime.
  - `protocol_helpers.py`: shared helper contracts for tool-call decoding and usage-shape normalization.
  - `protocol.py`: compatibility facade re-exporting protocol helper APIs.
  - `error_policy.py`: shared recoverable-error policy/result primitives and contextual fallback logging.
  - `run_orchestrator.py`: shared run-step state machine used by runtime sync/stream adapters and benchmark runner.
  - `execution.py`: agent execution-policy service (message intake/run lifecycle/context-token reads) plus benchmark/test execution facade methods.
  - `attachments.py`: message-to-canonical-file linkage helpers for attachment rows.
  - `attachment_content.py`: public attachment-content seam plus vision capability checks.
  - `attachment_content_pdf.py`: PDF text extraction, OCR fallback, render, and recoverable parse helpers.
  - `attachment_content_assembly.py`: attachment display-name, data-url, and model-content assembly helpers.
  - `message_history.py`: public thread-to-model message assembly seam.
  - `message_history_content.py`: attachment-backed user-content shaping and entity-category prompt context helpers.
  - `message_history_prefixes.py`: review-result and interruption-prefix history queries for the current turn.
  - `user_context.py`: account/user prompt-context normalization and truncation helpers.
  - `runtime.py`: public runtime facade and stable test/benchmark monkeypatch seams.
  - `runtime_support/`: grouped runtime internals split into run lifecycle and tool-turn preparation helpers.
  - `runtime_state.py`: run-event/tool-call persistence helpers used by runtime coordinator.
  - `entry_references.py`: shared entry-id alias, selector lookup, and public entry snapshot helpers.
  - `group_references.py`: shared group-id alias lookup plus public group summary/detail formatting for group tools and review payloads.
  - `proposals/`: proposal-family helpers split into `common.py`, `catalog.py`, `entries.py`, `groups.py`, the `group_memberships/` package (`common.py`, `validation.py`, `handlers.py`), family-owned normalization modules plus a small `normalization.py` registry, and `pending.py`.
  - `proposal_metadata.py`: canonical proposal domain/action/tool-name mapping shared by list/history/review surfaces.
  - `tool_runtime.py`: thin public seam for tool contracts and execution entrypoints.
  - `tool_runtime_support/`: grouped tool-runtime internals split into tool definitions, schema inlining, family registries, merged registry composition, and retry/error execution policy.
  - `benchmark_interface.py`: stable benchmark execution contract returning normalized predictions/trace data.
  - `change_contracts/`: proposal payload contracts split into `catalog.py`, `entries.py`, `groups.py`, shared normalization in `common.py`, and registry/patch helpers in `__init__.py` + `patches.py`.

### Backend Tests (`/backend/tests`)

- `conftest.py`: test app/client setup with isolated SQLite DB.
- `agent_test_utils.py`: shared agent test harness helpers (model patching, thread/message flows, SSE parsing, PDF fixture builders).
- `test_entries.py`: entry/group/delete behavior tests, including typed-group validation and principal scoping.
- `test_finance.py`: reconciliation and dashboard aggregation tests.
- `test_migrations_core.py`: migration regression coverage, including legacy link-to-typed-group conversion.
- `test_taxonomies.py`: taxonomy endpoints and tag/entity category assignment behavior tests.
- `test_auth_boundaries.py`: app-level principal dependency boundary regression tests.
- `test_workspace.py`: current-user workspace API coverage for snapshot scoping and disabled-mode lifecycle semantics.
- `test_benchmark_seed_workflows.py`: benchmark/seed workflow regression tests.

## Frontend (`/frontend`)

- `package.json`: npm scripts and frontend dependencies.
- `package-lock.json`: locked npm dependencies.
- `vite.config.ts`: dev server config and API proxy.
- `vitest.config.ts`: frontend unit test runner configuration (`jsdom` + RTL setup).
- `tsconfig.json`: TypeScript compiler settings.
- `index.html`: Vite app shell.
- `README.md`: thin frontend-local navigation doc that points to canonical docs.
- `docs/`: package-local frontend subsystem docs (`README.md`, `app_shell_and_routing.md`, `client_and_state.md`, `workspaces.md`, `agent_workspace.md`, `styles_and_operations.md`).

### Frontend Source (`/frontend/src`)

- `main.tsx`: React root and providers, including the auth provider.
- `App.tsx`: top-level shell layout (sidebar + content) and route map.
- `styles.css`: global styling including sidebar and app-shell classes.
- `test/`: frontend test setup, typed fixture factories, and shared query-client test renderer.

#### Components (`/frontend/src/components`)

- `Sidebar.tsx`: collapsible left-panel navigation with icon+label links and the active-principal switcher.
- `MetricCard.tsx`: reusable metric container.
- `LineChart.tsx`: legacy SVG daily expense chart helper (dashboard now uses Recharts).
- `GroupGraphView.tsx`: React Flow-based graph rendering for entry groups.
- `GroupEditorModal.tsx`: create/rename dialog for named typed groups.
- `GroupDetailModal.tsx`: wide group-detail modal for derived graph inspection and direct-member management.
- `GroupMemberEditorModal.tsx`: add-member dialog that submits the typed group-member target payload shared with the backend.
- `TagMultiSelect.tsx`: Notion-style chip/dropdown multi-select for entry tags.
- `DeleteConfirmDialog.tsx`: shared destructive confirmation dialog for account, entity, and tag deletes.
- `EntryEditorModal.tsx`: shared popup for entry create/edit, including direct-group assignment and split-role selection when needed.
- `MarkdownBlockEditor.tsx`: BlockNote wrapper for markdown + pasted images.
- `agent/AgentRunBlock.tsx`: extracted run activity/summary renderer used by `AgentPanel`.
- `agent/activity.ts`: extracted run/activity derivation helpers for agent timeline state.
- `agent/review/model.ts`: review-item summaries, proposal-domain grouping, and shared change-type labels.
- `agent/panel/*`: agent panel presentation layer (`AgentThreadList`, `AgentThreadPanel`, `AgentTimeline`, `AgentComposer`, `AgentThreadUsageBar`, `AgentAttachmentPreviewDialog`) plus the coordinator hooks (`useAgentPanelController`, `useAgentPanelQueries`, `useAgentThreadActions`, `useAgentComposerRuntime`), composer-runtime support hooks (`useAgentComposerStreamState`, `useAgentComposerActions`), panel-local hooks (`useResizablePanel`, `useStickToBottom`, `useAgentDraftAttachments`), and type/format helpers.
- `agent/review/*`: thread-review modal shell plus split modal presentation modules (`ReviewModalHeader`, `ReviewModalControls`, `ReviewActiveItemCard`, `ReviewModalFooter`), the review controller plus support hooks (`useAgentReviewEditorResources`, `useAgentReviewDraftState`), split TOC/catalog/group editor modules (`ReviewTocSection.tsx`, `ReviewCatalogEditors.tsx`, `ReviewGroupEditors.tsx`) behind the `ReviewEditors.tsx` export seam, draft packages (`drafts/common.ts`, `entries.ts`, `catalog.ts`, `memberships.ts`), and diff packages (`diff/core.ts`, `domains.ts`).

#### Pages (`/frontend/src/pages`)

- `DashboardPage.tsx`: tabbed interactive analytics dashboard (overview/daily/breakdowns/insights) backed by Recharts.
- `LoginPage.tsx`: password sign-in page for the browser app.
- `AdminPage.tsx`: admin-only user/session management workspace.
- `WorkspacePage.tsx`: current-user workspace IDE shell with iframe launch and minimal degraded/mobile fallback states.
- `SettingsPage.tsx`: thin runtime-settings page shell that composes the `features/settings` controller and section modules.
- `EntriesPage.tsx`: list/filter/delete entries and open popup create/edit editor.
- `EntryDetailPage.tsx`: show entry detail, direct-group context, direct-group graph, and popup editing.
- `GroupsPage.tsx`: first-class group workspace with a table-first browser and detail modal for group editing.
- `GroupsPage.test.tsx`: page-level integration test for table-first group browsing and detail-modal opening.
- `AccountsPage.tsx`: thin page orchestrator that composes accounts feature modules.
- `PropertiesPage.tsx`: thin page orchestrator that composes properties feature modules.
- `AccountsPage.test.tsx`: page-level integration tests for account create, snapshot, and delete flows.
- `EntriesPage.test.tsx`: page-level integration tests for missing-entity markers in the entries table.
- `PropertiesPage.test.tsx`: page-level integration tests for taxonomy and property delete flows.
- `WorkspacePage.test.tsx`: page-level integration tests for workspace IDE launch, degraded states, and narrow-screen fallback.

#### Feature Modules (`/frontend/src/features`)

- `auth/`
  - `storage.ts`: localStorage-backed bearer token helpers.
  - `AuthProvider.tsx`: app-wide auth context, `/auth/me` bootstrap, and best-effort workspace auto-start after auth restoration.
  - `AuthSessionCard.tsx`: sidebar logout control that reflects the signed-in user.
- `accounts/`
  - `useAccountsPageModel.ts`: query/mutation orchestration, derived state, and action handlers.
  - `AccountsTableSection.tsx`: account table/search/selection UI.
  - `ReconciliationSection.tsx`: account reconciliation summary UI.
  - `SnapshotCreatePanel.tsx`: snapshot-create form shown in the account edit modal sidebar.
  - `SnapshotHistoryTable.tsx`: snapshot history table shown in the account edit modal history column.
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
- `settings/`
  - `useSettingsPageModel.ts`: runtime-settings query/mutation orchestration, tab state, and form patch actions.
  - `formState.ts`: runtime-settings form hydration, validation, and update-payload construction.
  - `SettingsToolbar.tsx`, `SettingsGeneralSection.tsx`, `SettingsAgentSection.tsx`, `ResetSettingsDialog.tsx`: settings workspace UI sections and dialogs.
  - `constants.ts`, `types.ts`: shared settings field ids, tab definitions, and form-state contracts.

#### Frontend Lib (`/frontend/src/lib`)

- `types.ts`: shared TS API/data types.
- `api.ts`: fetch wrappers and API request functions, including shared bearer-token injection plus admin/auth helpers.
- `types/workspace.ts`: workspace snapshot and recursive file-tree contracts.
- `api/workspace.ts`: current-user workspace snapshot and start/stop request helpers.
- `format.ts`: money formatting and date helpers.
- `queryKeys.ts`: centralized TanStack Query key factory for all domains.
- `queryInvalidation.ts`: shared cache invalidation rules after mutations/review actions, including group-driven entry/group refresh.

## Supporting Directories

- `/docs`: architecture and engineering documentation.
  - `README.md`: canonical index for the docs tree.
  - `backend_index.md`, `frontend_index.md`, `ios_index.md`, `telegram_index.md`, `api.md`: subsystem index docs.
  - `/api`: focused API topic docs.
  - `/features`: cross-cutting feature docs and feature index.
  - `documentation_system.md`: source-of-truth matrix + anti-drift workflow.
  - `/completed_tasks`: archived task docs, retrospectives, and fix logs.
  - `features/entry_lifecycle.md`: entry-domain flow map.
  - `features/dashboard_analytics.md`: dashboard flow map.
  - `features/account_reconciliation.md`: account workspace + snapshot/reconciliation flow map.
  - `/adr`: architecture decision records.
- `/tasks`: active implementation plans, temporary caveats, and migration checklists.
- `/skills/frontend-ui-builder/SKILL.md`: project-local frontend build skill focused on shared layout primitives, explicit scroll/overlay ownership, concise copy, and preserving bespoke high-value interactions.
- `/skills/desloppify-maintenance/SKILL.md`: project-local desloppify workflow skill for exclude review, queue-driven fix loops, and standards-log updates during cleanup campaigns.
- `/scripts/seed_defaults.py`: reset local DB and seed default tags, entity categories, and accounts; optional user-memory copy now has explicit error policy (`best_effort` default, optional `fail_fast`) and shared DB factory usage.
- `/scripts/seed_demo.py`: local seed dataset generation.
- `/scripts/bootstrap_admin.py`: create or reset an admin password-backed login and upgrade the database to head when needed.
- `/scripts/setup_shared_env.sh`: copies `.env` (or `.env.example`) to `~/.config/bill-helper/.env` for cross-worktree secret sharing.
- `/scripts/check_docs_sync.py`: docs consistency checks (migration refs + stale term detection + index links).
- `/.data` (runtime, legacy): per-worktree SQLite DB override location (ignored in git). Default data location is `~/.local/share/bill_helper/`.

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
