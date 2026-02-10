# Agent Capability Upgrade TODO Plan

## Goal

Upgrade the billing agent from create-only proposal flow to full proposal coverage and stronger execution reliability while keeping human review in the loop.

## Finalized Decisions (from discussion)

1. Tags/entities should support full CRUD proposal capabilities.
2. Entry target selection (for update/delete) should use: `date + amount_minor + from_entity + to_entity + name`.
3. No domain resource IDs should appear in tool interfaces shown to the model.
4. Add config for default currency (owner default currency) using `BILL_HELPER_DEFAULT_CURRENCY_CODE`.
5. `from_entity` and `to_entity` are required in create-entry proposals.
6. Query behavior should support both exact and fuzzy matching, with exact ranked higher.
7. Consolidate to one `list_entries` tool with richer query filters (remove separate `search_entries`).
8. Keep the run model simple; choose the most reliable continuation approach without adding unnecessary complexity.
9. Agent behavior after review should be feedback-driven by user comments/review results; when feedback is missing, agent should explore gaps and improve proposals.
10. For this work item now: create this new TODO doc only.
11. Tag/entity update proposal payload should support rename + category only.
12. Tag/entity delete should use detach/nulling behavior and review UI should show all affected entries.

## Scope

### Tool surface redesign

- Replace ID-oriented proposal args with natural-key/domain args only.
- Remove `list_accounts` tool.
- Update `list_entities` docs/description to instruct using `category="account"` for account-like entities.

### Proposal capability completeness

- Entries: proposal CRUD.
- Tags: proposal CRUD.
- Entities: proposal CRUD.

### Reliability and loop quality

- Add retry/backoff configuration with `tenacity`.
- On tool failures, return structured failure context to the model so it can choose to continue or escalate.
- Add reviewed-result continuation loop so proposal review outcomes are fed back into the next agent turn.

## Target Tool Contract (V2)

## Read tools

### `list_entries`

Single query/list tool with optional filters:

- `date` (exact)
- `start_date`
- `end_date`
- `name`
- `from_entity`
- `to_entity`
- `tags` (list)
- `kind`
- `limit`

Matching/ranking:

- Prefer exact matches first.
- Include fuzzy matches after exact (case-insensitive contains).
- Return deterministic ordering.

Output:

- No domain IDs in model-facing text output.
- Include enough fields for disambiguation (`date`, `name`, `amount_minor`, `currency_code`, `from_entity`, `to_entity`, `tags`).

### `list_tags`

Filters:

- `name`
- `category`
- `limit`

Output:

- Include `name`, `category` (no IDs in model-facing tool contract/output text).
- Exact-first ranking, then fuzzy.

### `list_entities`

Filters:

- `name`
- `category`
- `limit`

Output:

- Include `name`, `category` (no IDs in model-facing tool contract/output text).
- Exact-first ranking, then fuzzy.
- Tool description note: use `category="account"` when looking for account entities.

## Proposal tools

### Create

- `propose_create_tag(name, category)`  
  - remove: `color`, `rationale`
  - `category` required

- `propose_create_entity(name, category)`  
  - remove: `rationale`
  - `category` required

- `propose_create_entry(kind, date, name, amount_minor, currency_code?, from_entity, to_entity, tags, markdown_notes)`  
  - remove legacy args: `account_id`, `from_entity_id`, `to_entity_id`, `owner_user_id`, `owner`, `rationale`, `duplicate_check_note`
  - `currency_code` optional; fallback to new default currency config
  - `from_entity`, `to_entity` required

### Update/Delete (new)

- Entries:
  - `propose_update_entry(selector, patch)`
  - `propose_delete_entry(selector)`
  - selector fields: `date`, `amount_minor`, `from_entity`, `to_entity`, `name`

- Tags:
  - `propose_update_tag(name, patch)`
  - `propose_delete_tag(name)`
  - `patch` fields limited to: `name`, `category`

- Entities:
  - `propose_update_entity(name, patch)`
  - `propose_delete_entity(name)`
  - `patch` fields limited to: `name`, `category`

Notes:

- No domain IDs in tool args.
- Backend may still use internal IDs internally after lookup.
- Ambiguous selector matches should produce explicit tool errors with candidate summaries (no IDs exposed to model).
- Delete semantics for tag/entity:
  - detaching/nulling references is allowed
  - proposal/apply preview should include impacted entry summaries so review modal shows blast radius before approval

## Data/Model Work

- Extend `AgentChangeType` enum and handlers for update/delete variants.
- Add payload schemas/validators for each proposal type.
- Keep current review/apply audit trail behavior.
- Preserve unique entity name invariants on create/update paths.

## Runtime/Retry Work

- Introduce retry config fields (proposed names):
  - `agent_retry_max_attempts`
  - `agent_retry_initial_wait_seconds`
  - `agent_retry_max_wait_seconds`
  - `agent_retry_backoff_multiplier`
- Apply `tenacity` to:
  - model completion calls
  - tool execution wrapper (with bounded retries for transient failures)
- On terminal tool failure:
  - persist failed tool call
  - pass structured failure result back to model
  - let model decide: continue with alternative steps or explicitly escalate to user.

## Review Continuation Loop (Agent In The Loop)

Problem today:

- Proposal review outcomes are handled in UI/backend but are not reliably fed back as structured context into the next model turn.

Target flow:

1. Agent proposes changes via `propose_*` tools.
2. User reviews items (approve/reject/edit) and may provide comments.
3. On next send, backend prepends reviewed-result context before user feedback in the new user message (review diffs + comments + statuses).
4. Agent decides next actions (improve proposals, gather more facts, or ask user for missing info).
5. Repeat until user is satisfied.

Behavior rule when user feedback is absent:

- Prompt agent to inspect failures/rejections/remaining ambiguity and propose improved changes proactively.

Implementation sketch:

- Add a review-summary builder from `AgentChangeItem` + `AgentReviewAction`.
- Build review summary text in `build_llm_messages` and prepend it before the current user feedback message (no per-turn system prompt mutation).
- Update system prompt to explicitly handle reviewed-result continuation.

## Files Expected To Change (implementation phase)

- Backend:
  - `backend/services/agent/tools.py`
  - `backend/services/agent/runtime.py`
  - `backend/services/agent/prompts.py`
  - `backend/services/agent/change_apply.py`
  - `backend/services/agent/message_history.py`
  - `backend/config.py`
  - `backend/enums.py`
  - `backend/models.py` (+ migration if enum/storage changes require it)
- Tests:
  - `backend/tests/test_agent.py`
  - additional tests for selector ambiguity, retry behavior, and continuation context
- Docs:
  - `docs/agent-billing-assistant.md`
  - `docs/backend.md`
  - `docs/api.md`
  - `docs/architecture.md`
  - `README.md` (if externally visible behavior/flow changes)

## Acceptance Criteria

1. Model-facing tool interfaces and outputs do not expose domain resource IDs.
2. `list_accounts` is removed from available agent tools.
3. `list_entities` supports `category` and clearly covers account lookup via `category="account"`.
4. Tag/entity list outputs include categories.
5. Entry/tag/entity proposal tools cover CRUD and validate inputs correctly.
6. Entry create proposal args exactly match agreed contract.
7. Tool failures are returned to model context and do not always force immediate user-facing termination.
8. Retry/backoff is configurable and covered by tests.
9. Reviewed proposal outcomes are injected into continuation turns.
10. Agent can iteratively improve proposals after user review/comments.

## Risks / Constraints

- Removing IDs from tool interfaces increases ambiguity; selector matching and disambiguation UX must be strict.
- Expanding `AgentChangeType` likely requires migration and careful backward compatibility for existing review records.
- Prompt complexity may increase token use; continuation summary should be compact and deterministic.

## Rollout Strategy

1. Ship tool contract + backend handlers behind tests first.
2. Add retry/failure-to-agent behavior.
3. Add review-continuation via user-message augmentation.
4. Update docs and run docs sync checker in implementation PR:

```bash
uv run python scripts/check_docs_sync.py
```
