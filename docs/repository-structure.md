# Repository Structure (Current)

## Root

- `.gitignore`: ignores venv, build outputs, runtime data, test cache.
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
- `groups.py`: graph view of an entry group.
- `dashboard.py`: monthly analytics endpoint.
- `agent.py`: append-only agent thread/message/run/review endpoints.
- `settings.py`: runtime settings read/update endpoints for user overrides with env fallback.

### Backend Services (`/backend/services`)

- `entries.py`: tag handling and entry soft-delete helper.
- `tags.py`: tag color helpers (normalization and random default color generation).
- `entities.py`: entity normalization and lookup helpers.
- `users.py`: user normalization, lookup, and current-user helpers.
- `groups.py`: connected-component recomputation for `group_id`.
- `finance.py`: reconciliation, CAD dashboard analytics, projections, and chart-ready breakdown aggregations.
- `serializers.py`: ORM-to-schema mapping helpers.
- `taxonomy.py`: shared taxonomy normalization, term assignment, and usage-count helpers.
- `runtime_settings.py`: resolves effective runtime settings from persisted overrides + env defaults.
- `agent/`: agent runtime, tool execution, serialization, prompt/model adapters, and review apply handlers.

### Backend Tests (`/backend/tests`)

- `conftest.py`: test app/client setup with isolated SQLite DB.
- `test_entries.py`: entry/link/group/delete behavior tests.
- `test_finance.py`: reconciliation and dashboard aggregation tests.
- `test_taxonomies.py`: taxonomy endpoints and tag/entity category assignment behavior tests.

## Frontend (`/frontend`)

- `package.json`: npm scripts and frontend dependencies.
- `package-lock.json`: locked npm dependencies.
- `vite.config.ts`: dev server config and API proxy.
- `tsconfig.json`: TypeScript compiler settings.
- `index.html`: Vite app shell.
- `README.md`: frontend-local change map and UI workflow notes.

### Frontend Source (`/frontend/src`)

- `main.tsx`: React root and providers.
- `App.tsx`: top-level shell layout (sidebar + content) and route map.
- `styles.css`: global styling including sidebar and app-shell classes.

#### Components (`/frontend/src/components`)

- `Sidebar.tsx`: collapsible left-panel navigation with icon+label links.
- `MetricCard.tsx`: reusable metric container.
- `LineChart.tsx`: legacy SVG daily expense chart helper (dashboard now uses Recharts).
- `GroupGraphView.tsx`: SVG graph rendering for entry groups.
- `TagMultiSelect.tsx`: Notion-style chip/dropdown multi-select for entry tags.
- `EntryEditorModal.tsx`: shared popup for entry create/edit.
- `MarkdownBlockEditor.tsx`: BlockNote wrapper for markdown + pasted images.

#### Pages (`/frontend/src/pages`)

- `DashboardPage.tsx`: tabbed interactive analytics dashboard (overview/daily/breakdowns/insights) backed by Recharts.
- `SettingsPage.tsx`: responsive runtime settings workspace (general, agent runtime, reliability).
- `EntriesPage.tsx`: list/filter/delete entries and open popup create/edit editor.
- `EntryDetailPage.tsx`: manage links/group graph and open popup editor for updates.
- `AccountsPage.tsx`: create/update accounts, snapshot management, reconciliation view.
- `PropertiesPage.tsx`: database-style management for users, entities, tags, and currency catalog placeholder.

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
- `/scripts/seed_demo.py`: local seed dataset generation.
- `/scripts/check_docs_sync.py`: docs consistency checks (migration refs + stale term detection + index links).
- `/.data` (runtime): SQLite DB (ignored in git).
