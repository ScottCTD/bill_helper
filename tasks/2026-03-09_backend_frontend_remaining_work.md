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
- Frontend `AgentPanel.test.tsx` passes.
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

The next major backend batch should reduce the remaining proposal/runtime cleanup after the contract split and shared thread-proposal query cleanup:

- `review::.::holistic::abstraction_fitness::internal_tool_args_barrel::a034bd44`
- `review::.::holistic::abstraction_fitness::proposal_normalization_switchboard::48c8c386`
- `review::.::holistic::api_surface_coherence::tool_result_status_shape_drift::a7d7b0fc`
- `review::.::holistic::authorization_consistency::agent_entry_scope_bypass::328518a7`

Recommended direction:

- stop routing internal callers through `backend/services/agent/tool_args/__init__.py`
- separate pending-review normalization from proposal creation logic
- unify tool result status around one canonical contract
- apply owner scoping in agent entry lookup/apply helpers the same way normal entry routes do

### 2. Service/API contract cleanup outside the agent

The next backend cleanup after the agent contract split should reduce duplicated contract shapes and schema/service drift:

- `review::.::holistic::ai_generated_debt::contract_validator_boilerplate::205d64d7`
- `review::.::holistic::ai_generated_debt::duplicate_runtime_settings_update_models::1af2d886`
- `review::.::holistic::cross_module_architecture::service_schema_entanglement::...` follow-up items now showing as read-side/API-shape drift in the new review set
- `review::.::holistic::api_surface_coherence::group_membership_target_overload::10d4e80e`
- `review::.::holistic::api_surface_coherence::sibling_resource_services_mix_command_model_apis_with_primitive_heavy_mutation_signatures::9119f48e`

Recommended direction:

- use one field registry or shared spec for runtime settings write/read shapes
- continue moving services onto service-local command/result types
- reduce group membership “entry vs child group” exclusivity into clearer target contracts
- standardize mutation APIs so sibling services are not half command-model, half primitive-heavy

### 3. Router/service consistency cleanup

The router split landed, but the review still flags backend HTTP consistency debt:

- `review::.::holistic::ai_generated_debt::router_policy_translation_boilerplate::48b86e1a`
- `review::.::holistic::design_coherence::router_service_boundary_blur::...`
- `review::.::holistic::error_consistency::*` items for accounts, groups, and taxonomy
- `review::.::holistic::authorization_consistency::*` items around catalog/global usage exposure and auth drift

Recommended direction:

- add one shared `PolicyViolation` -> HTTP translation helper for CRUD routers
- continue moving router-owned read aggregation into services
- replace message-text HTTP mapping with typed domain exceptions
- re-check agent and catalog read endpoints for owner scoping and authorization consistency

### 4. Frontend monolith follow-up

`AgentPanel.tsx` is now thin, but the next frontend cleanup should target the remaining large review/editor modules:

- `frontend/src/features/agent/review/AgentThreadReviewModal.tsx` (`1609` lines)
- `frontend/src/features/agent/panel/useAgentPanelController.ts` (`1151` lines)
- `frontend/src/features/agent/review/drafts.ts` (`829` lines)
- `frontend/src/features/agent/review/diff.ts` (`732` lines)
- `frontend/src/pages/SettingsPage.tsx` (`763` lines)

Recommended direction:

- split the review modal into navigation shell, card renderer, action bar, and editing hooks
- split `useAgentPanelController.ts` further into stream state, thread workspace state, and send/review action hooks
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

1. Remove internal `tool_args` barrel usage and reduce pending-review normalization switchboards.
2. Unify router `PolicyViolation` translation and typed error mapping across CRUD routers.
3. Split `frontend/src/features/agent/review/AgentThreadReviewModal.tsx`.
4. Split `frontend/src/features/agent/panel/useAgentPanelController.ts`.
5. Attack test-health items around the new service seams.

## Latest Major Commits From This Pass

- `91963bd` `Split agent read tools into a package`
- `70e42b9` `Extract agent runtime loop adapters`
- `7c5d72b` `Split agent router by endpoint family`
- `b2b958e` `Refactor agent panel into controller and helpers`
