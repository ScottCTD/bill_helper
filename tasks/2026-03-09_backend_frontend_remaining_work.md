# Backend + Frontend Remaining Work

Date: 2026-03-09

This document captures the remaining backend/frontend architecture work after the March 9 refactor pass that:

- split agent proposal/apply/review/read handlers into packages
- extracted the runtime loop from `backend/services/agent/runtime.py`
- split the agent router by endpoint family
- reduced `frontend/src/features/agent/AgentPanel.tsx` to a render shell backed by a controller hook and helper module

Excluded from this pass and from the current `desloppify` scope:

- `benchmark/`
- `ios/`
- `telegram/`
- `docs/`
- `scripts/`
- `skills/`
- `alembic/`

## Current Baseline

Verification:

- Backend targeted compile/test batches passed for each refactor batch.
- Full backend suite baseline after the refactors: `292 passed, 8 failed`.
- The 8 backend failures are unchanged, pre-existing runtime-settings/default-model expectation failures around `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0`.
- Frontend `AgentThreadReviewModal.test.tsx` and `AgentPanel.test.tsx` pass.
- Frontend production build passes.
- `uv run python scripts/check_docs_sync.py` passes.

Desloppify snapshot after forced rescan and forced batch review rerun:

- strict score: `70.6/100`
- objective score: `85.3/100`
- open in-scope issues: `252`
- queue items: `151`
- open review issues: `68`
- biggest mechanical drag: test health `45.6%`

## Highest-Priority Remaining Architecture Work

### 1. Agent contract decomposition

The next major backend batch should reduce the remaining proposal/runtime cleanup after the contract split, shared thread-proposal query cleanup, direct tool-arg ownership cleanup, and payload-normalization split:

- `review::.::holistic::api_surface_coherence::tool_result_status_shape_drift::a7d7b0fc`
- `review::.::holistic::authorization_consistency::agent_entry_scope_bypass::328518a7`

Recommended direction:

- unify tool result status around one canonical contract
- apply owner scoping in agent entry lookup/apply helpers the same way normal entry routes do

### 2. Service/API contract cleanup outside the agent

The next backend cleanup after the agent contract split should continue reducing read-side/API-shape drift:

- `review::.::holistic::cross_module_architecture::service_schema_entanglement::...` follow-up items now showing as read-side/API-shape drift in the new review set

Recommended direction:

- continue moving services onto service-local command/result types
- keep group/user write paths on the same command/patch convention already used by account/entity/tag mutations
- keep read-side services off API schemas and duplicate response assemblers

### 3. Router/service consistency cleanup

The router split landed, but the review still flags backend HTTP consistency debt:

- `review::.::holistic::design_coherence::router_service_boundary_blur::...`
- `review::.::holistic::error_consistency::*` items for accounts, groups, and taxonomy
- `review::.::holistic::authorization_consistency::*` items around catalog/global usage exposure and auth drift

Recommended direction:

- continue moving router-owned read aggregation into services
- replace message-text HTTP mapping with typed domain exceptions
- re-check agent and catalog read endpoints for owner scoping and authorization consistency

### 4. Frontend follow-up after the shell/controller split

The thread review modal and panel controller split are now in place:

- `frontend/src/features/agent/review/AgentThreadReviewModal.tsx` is reduced to the modal/card shell
- `frontend/src/features/agent/review/useAgentThreadReviewController.ts` owns review queries, draft maps, navigation, and review actions
- `frontend/src/features/agent/review/ReviewEditors.tsx` owns TOC navigation plus the proposal editor surfaces
- `frontend/src/features/agent/panel/useAgentComposerRuntime.ts` now owns the optimistic send/stream/composer runtime

The next frontend cleanup should target the remaining domain-heavy helpers and page orchestration:

- `frontend/src/features/agent/review/drafts.ts` (`829` lines)
- `frontend/src/features/agent/review/diff.ts` (`732` lines)
- `frontend/src/pages/SettingsPage.tsx` (`763` lines)

Recommended direction:

- carve `review/drafts.ts` into draft state reducers and patch-format helpers
- separate diff rendering primitives from finance/agent field-specific presenters
- move settings page orchestration into feature hooks, like the other page models in the repo

### 5. Test-health and dependency cleanup

The score and queue still show that test health is the biggest mechanical drag:

- `69` test-health items remain after the rescan/review import
- review also flagged default runtime dependencies that should not ship in the core app environment

Recommended direction:

- add direct service tests around the new agent contract splits instead of relying only on endpoint/regression coverage
- move notebook/review-only packages out of default runtime dependencies
- move `langfuse` behind an optional extra unless real runtime integration lands

### 6. Initialization and runtime coupling

Still-open structural issues worth addressing after the contract/router passes:

- `review::.::holistic::incomplete_migration::sessionlocal_alias_on_runtime_path::b6f7ec0d`
- `review::.::holistic::initialization_coupling::database_sessionlocal_import_snapshot::2a0c4b5f`
- `review::.::holistic::initialization_coupling::pricing_refresh_mutates_global_on_read_paths::0bf48229`
- `review::.::holistic::initialization_coupling::provider_env_global_mutation::5aaf680d`
- `review::.::holistic::logic_clarity::fail_open_env_validation::abe9b063`

Recommended direction:

- remove runtime dependence on `SessionLocal` snapshots
- make pricing serialization read-only and move refresh into explicit startup/background ownership
- isolate provider environment mutation behind one bootstrap/config adapter
- stop treating indeterminate environment validation as success

## Suggested Next Batch Order

1. Reduce pending-review normalization switchboards.
2. Unify router `PolicyViolation` translation and typed error mapping across CRUD routers.
3. Carve `frontend/src/features/agent/review/drafts.ts` into domain slices.
4. Split `frontend/src/features/agent/review/diff.ts` by renderer/field-family concerns.
5. Attack test-health items around the new service seams.

## Latest Major Commits From This Pass

- `91963bd` `Split agent read tools into a package`
- `70e42b9` `Extract agent runtime loop adapters`
- `7c5d72b` `Split agent router by endpoint family`
- `b2b958e` `Refactor agent panel into controller and helpers`
- pending current commit: split agent review modal and panel runtime ownership
