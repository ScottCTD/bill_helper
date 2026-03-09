# Backend Domain And HTTP

## Domain Models

- `backend/models_finance.py`: ledger, account, entity, tag, taxonomy, and entry models
- `backend/models_agent.py`: thread, run, tool-call, change-item, and review models
- `backend/models_shared.py`: shared timestamp and UUID defaults

Core ledger models:

- `Account`, `AccountSnapshot`
- `Entry`, `EntryGroup`, `EntryGroupMember`
- `User`, `Entity`
- `Tag`, `EntryTag`
- `Taxonomy`, `TaxonomyTerm`, `TaxonomyAssignment`

Ledger model note:

- `Account` is an entity-root subtype after migration `0024_entity_root_accounts`
- `accounts.id == entities.id`; the old `accounts.entity_id` link no longer exists
- account semantics come from subtype membership in `accounts`, not from `entities.category = 'account'`

Agent models:

- `AgentThread`
- `AgentMessage`
- `AgentMessageAttachment`
- `AgentRun`
- `AgentToolCall`
- `AgentChangeItem`
- `AgentReviewAction`

## Schemas

- `backend/schemas_finance.py`: accounts, entries, groups, dashboard, and settings contracts
- `backend/schemas_agent.py`: thread, message, run, change-item, and review contracts

Important read models:

- `GroupSummaryRead` for `GET /groups`
- `GroupGraphRead` for `GET /groups/{group_id}` with entry-node `amount_minor` and `currency_code` for UI stats
- `EntryRead` / `EntryDetailRead` for entry list/detail reads with `direct_group`, `direct_group_member_role`, and `group_path`
- `RuntimeSettingsRead` for `/settings`

## Core Services

- `backend/services/accounts.py`
- `backend/services/entries.py`
  - owns typed entry create/update command workflows, entity/user/group resolution, and soft-delete cleanup
- `backend/services/entities.py`
- `backend/services/users.py`
- `backend/services/groups.py`
- `backend/services/finance.py`
  - owns reconciliation math and dashboard analytics sections:
    - configured-currency monthly KPIs
    - daily vs non-daily spend series
    - monthly trend rollups
    - from/to/tag breakdowns
    - weekday distribution
    - current-month projection
- `backend/services/crud_policy.py`
  - shared validation, uniqueness/conflict checks, and policy-violation translation helpers
- `backend/services/access_scope.py`
  - principal-scoped query and authorization helpers for owned resources
- `backend/services/bootstrap.py`
  - schema bootstrap helpers used by local reset, seed, and benchmark scripts
- `backend/services/serializers.py`
- `backend/services/taxonomy.py`
- `backend/services/runtime_settings.py`
  - resolves effective runtime settings from DB overrides plus env defaults
- `backend/services/runtime_settings_normalization.py`
  - single-source normalization shared by schemas and runtime resolution

Current account/entity helpers:

- `accounts.py` creates, renames, and deletes the shared account/entity root
- `entities.py` blocks generic mutation of account-backed roots and preserves denormalized entry labels on delete
- `tags.py` supports delete while referenced and relies on `entry_tags` cascade cleanup

Service conventions:

- `ensure_*` helpers are explicit mutating lookup or create paths and may write plus `flush`
- `read_*` and `find_*` helpers are read-only
- shared CRUD validation lives in `crud_policy.py`
- shared owner/admin policy lives in `access_scope.py`
- package `__init__.py` files stay marker-only and should not become barrel re-export modules
- application code and tests should import direct domain modules (`*_finance`, `*_agent`) instead of rebuilding aggregate facades

## Routers

Core routers:

- `accounts.py`
- `entries.py`
- `groups.py`
- `dashboard.py`
- `users.py`
- `entities.py`
- `tags.py`
- `taxonomies.py`
- `currencies.py`
- `settings.py`

Router behavior:

- account, entry, and group handlers use shared principal-scoped helpers from `backend/services/access_scope.py`
- `backend/routers/entries.py` stays at HTTP parsing/translation while `backend/services/entries.py` owns entry create/update orchestration
- non-admin principals are restricted to their own owned resources; admin principal retains cross-user visibility and mutation
- `groups.py` exposes first-class group CRUD, membership mutation, and derived group graphs
- `dashboard.py` is principal-scoped by visible accounts and entries
- `accounts.py` includes principal-scoped delete in addition to create, update, snapshots, and reconciliation
- `entities.py` includes admin-only delete for non-account entities and returns `409` for account-backed roots
- `tags.py` includes admin-only delete and succeeds even when entries still reference the tag
- `entities.py`, `tags.py`, and `taxonomies.py` mutations require admin principal
- `entities.py` category responses resolve through taxonomy assignment state so term renames are reflected immediately

Settings router:

- `backend/routers/settings.py`
- endpoints:
  - `GET /api/v1/settings`
  - `PATCH /api/v1/settings`

## Related Docs

- `docs/api/core-ledger.md`
- `docs/api/catalogs-and-settings.md`
- `docs/data-model.md`
