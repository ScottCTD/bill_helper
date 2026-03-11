# Backend Domain And HTTP

## Domain Models

- `backend/models_finance.py`: ledger, account, entity, tag, taxonomy, filter-group, and entry models
- `backend/models_agent.py`: thread, run, tool-call, change-item, and review models
- `backend/models_settings.py`: runtime settings override model
- `backend/contracts_groups.py`: shared group write contracts and typed group-member target payloads
- `backend/contracts_users.py`: shared user write contracts
- `backend/models_shared.py`: shared timestamp and UUID defaults

Core ledger models:

- `Account`, `AccountSnapshot`
- `FilterGroup`
- `Entry`, `EntryGroup`, `EntryGroupMember`
- `User`, `Entity`
- `Tag`, `EntryTag`
- `Taxonomy`, `TaxonomyTerm`, `TaxonomyAssignment`

Ledger model note:

- `Account` is an entity-root subtype after migration `0024_entity_root_accounts`
- `accounts.id == entities.id`; the old `accounts.entity_id` link no longer exists
- account semantics come from subtype membership in `accounts`, not from `entities.category = 'account'`
- `User.is_admin` is the persisted role gate for admin-only routes and cross-user visibility

Agent models:

- `AgentThread`
- `AgentMessage`
- `AgentMessageAttachment`
- `AgentRun`
- `AgentToolCall`
- `AgentChangeItem`
- `AgentReviewAction`

## Auth Boundary

- `backend/auth/contracts.py`: request-principal contract plus header-name constant
- `backend/auth/dev_session.py`: development-session principal normalization and bootstrap-admin-name rules
- `backend/auth/dependencies.py`: FastAPI dependencies that require `X-Bill-Helper-Principal`, materialize the backing user row, and enforce admin-only access
- `backend/services/principals.py`: resolves request principals from the explicit header-backed session and persisted user role

## Schemas

- `backend/schemas_finance.py`: accounts, entries, groups, filter-group, and dashboard contracts
- `backend/schemas_agent.py`: thread, message, run, change-item, and review contracts
- `backend/schemas_settings.py`: runtime settings request/response contracts

Important read models:

- `GroupSummaryRead` for `GET /groups`
- `GroupGraphRead` for `GET /groups/{group_id}` with entry-node `amount_minor` and `currency_code` for UI stats
- `EntityRead` for `/entities` with usage counters plus a same-currency net aggregate (`net_amount_minor`, `net_amount_currency_code`) and a mixed-currency fallback flag
- `TagSummaryRead` for embedded entry-tag payloads, with `TagRead` reserved for `/tags` catalog responses that include `entry_count`
- `EntryRead` / `EntryDetailRead` for entry list/detail reads with `direct_group`, `direct_group_member_role`, `group_path`, and `TagSummaryRead[]` tags
- `FilterGroupRead` for `/filter-groups` with recursive include/exclude rule trees and plain-language summaries
- `RuntimeSettingsRead` for `/settings`

## Core Services

- `backend/services/accounts.py`
- `backend/services/entries.py`
  - owns typed entry create/update command workflows built around `EntityRef`/`UserRef` service refs, entity/user/group resolution, and soft-delete cleanup
- `backend/services/filter_groups.py`
  - owns default filter-group provisioning, principal-scoped filter-group CRUD, and persisted rule definitions
- `backend/services/filter_group_rules.py`
  - owns recursive filter-rule evaluation plus plain-language rule summaries
- `backend/services/entities.py`
- `backend/services/users.py`
- `backend/services/groups.py`
- `backend/contracts_groups.py`
  - shared group create/update contracts plus the typed `target` union used by `/groups/{group_id}/members`
- `backend/contracts_users.py`
  - shared user create/update contracts reused by schemas, routers, and services
- `backend/services/finance.py`
  - owns reconciliation math and dashboard analytics sections:
    - account reconciliation rollups derive account balance effect from account-entity flow (`from_entity_id` / `to_entity_id`) with `account_id` as a legacy fallback
    - configured-currency monthly KPIs
    - filter-group-powered daily and monthly spend series
    - monthly trend rollups
    - from/to/tag breakdowns
    - weekday distribution
    - current-month projection including projected filter-group totals
- `backend/services/crud_policy.py`
  - shared validation, uniqueness/conflict checks, and policy-violation translation helpers
- `backend/services/access_scope.py`
  - principal-scoped query and authorization helpers for owned resources
- `backend/services/bootstrap.py`
  - schema bootstrap helpers used by local reset, seed, and benchmark scripts
- `backend/services/finance_contracts.py`
  - service-owned account/entity/tag write commands shared by routers and agent apply flows
- `backend/services/serializers.py`
- `backend/services/taxonomy.py`
- `backend/services/runtime_settings.py`
  - resolves effective runtime settings from DB overrides plus env defaults
- `backend/contracts_settings.py`
  - shared runtime settings write/update contract used by both schemas and service patch models
- `backend/services/agent/proposals/`
  - proposal-family support split into shared helpers plus catalog, entries, groups, group-membership, normalization, and pending-admin modules
- `backend/validation/runtime_settings.py`
  - single-source normalization shared by schemas, tool-input models, and runtime resolution
- `backend/validation/agent_threads.py`
  - shared thread-title validation contract used by schemas, tool args, and thread services
- `backend/validation/finance_names.py`
  - shared name/category/tag normalization used by finance services, routers, and agent contracts
- `backend/validation/contract_fields.py`
  - shared normalized field types and non-empty patch base used by finance commands, agent change contracts, and tool-input models

Current account/entity helpers:

- `accounts.py` creates, renames, and deletes the shared account/entity root
- `entities.py` blocks generic mutation of account-backed roots and preserves denormalized entry labels on delete
- `tags.py` supports delete while referenced and relies on `entry_tags` cascade cleanup

Service conventions:

- `ensure_*` helpers are explicit mutating lookup or create paths and may write plus `flush`
- `read_*` and `find_*` helpers are read-only
- shared CRUD validation lives in `crud_policy.py`
- user-facing group mutation failures also use `PolicyViolation` now; router modules should not translate group `ValueError` strings by hand
- shared owner/admin policy lives in `access_scope.py`
- package `__init__.py` files stay marker-only and should not become barrel re-export modules
- application code and tests should import direct domain modules (`*_finance`, `*_agent`) instead of rebuilding aggregate facades

## Routers

Core routers:

- `accounts.py`
- `entries.py`
- `groups.py`
- `dashboard.py`
- `filter_groups.py`
- `users.py`
- `entities.py`
- `tags.py`
- `taxonomies.py`
- `currencies.py`
- `settings.py`

Router behavior:

- account, entry, and group handlers use shared principal-scoped helpers from `backend/services/access_scope.py`
- protected routes fail with `401` when `X-Bill-Helper-Principal` is absent; no backend fallback principal is injected anymore
- `backend/routers/entries.py` stays at HTTP parsing/translation while `backend/services/entries.py` owns entry create/update orchestration
- `backend/routers/entries.py` translates flat HTTP payload pairs (`from_entity_id` + `from_entity`, `owner_user_id` + `owner`, etc.) into typed service refs before calling `backend/services/entries.py`
- `backend/routers/accounts.py`, `entities.py`, and `tags.py` translate HTTP write schemas into `backend/services/finance_contracts.py` commands before calling service workflows
- `backend/routers/groups.py` and `users.py` now follow the same command/patch pattern through `backend/contracts_groups.py` and `backend/contracts_users.py`
- `backend/routers/tags.py`, `taxonomies.py`, `users.py`, and `dashboard.py` delegate read/write orchestration to their service modules instead of assembling persistence queries inline
- `backend/main.py` owns the shared FastAPI exception handler that turns `PolicyViolation` into JSON HTTP errors, so CRUD routers no longer repeat local translation blocks
- non-admin principals are restricted to their own owned resources; admin access is checked from `RequestPrincipal.is_admin`, not by matching the user name string
- `groups.py` exposes first-class group CRUD, membership mutation, and derived group graphs
- empty PATCH payloads for account, entity, tag, group, and user mutations are rejected consistently during request validation
- `POST /groups/{group_id}/members` accepts one typed `target` object (`entry` vs `child_group`) instead of sibling mutually-exclusive top-level ids
- `dashboard.py` is principal-scoped by visible accounts and entries
- `filter_groups.py` provisions and persists per-principal default filter groups on read, allows rule edits for defaults, and forbids renaming or deleting default group identities
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
