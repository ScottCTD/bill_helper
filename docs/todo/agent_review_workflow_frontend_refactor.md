# TODO: Agent Review Workflow and Frontend Review UX Refactor

## Objective

Refactor the agent review loop so unresolved proposals stay editable across user turns, while improving the review UI and tool-call transparency for human readability.

## Current Gaps

- Review modal actions are asymmetric:
  - no `Reject All` action
  - `Approve & Next` adds little value compared with direct `Approve`
- Diff rendering is still too JSON-shaped for human review:
  - scalar strings render with quotes (`currency_code: "CAD"`)
  - entry amounts are shown as `amount_minor` instead of human-readable significant digits
- Agent proposal flow is blocked when pending items exist in earlier runs of the same thread:
  - `backend/services/agent/tools.py` currently blocks `propose_*` tools when pending items exist outside the current run.
- Pending proposal mutation is not available to the agent:
  - there is no tool to update a pending proposal by proposal id.
- Proposal tool outputs do not return proposal ids.
- Tool-call details in the frontend focus on stored JSON (`input_json`, `output_json`) instead of the exact text content that was provided back to the model (`role=tool` message content).

## Proposed Behavior

1. Review modal action updates:
  - add `Reject All` with confirmation dialog (parallel to existing `Approve All` flow)
  - remove `Approve & Next` from default actions
  - keep single-item `Approve` and `Reject` actions
2. Diff readability updates:
   - render scalar text values without JSON quotes
   - render entry amounts in major units for humans (example: `12.34 CAD`) while preserving minor-unit value as secondary metadata when needed
   - render entry fields in a stable, user-friendly order instead of raw key-sorted JSON order
   - render field names with product-oriented labels where applicable
3. Pending proposal lifecycle:
  - keep existing `PENDING_REVIEW` status as the canonical pending state
  - when users send follow-up messages without fully reviewing prior proposals, unresolved proposals remain pending and editable
  - remove proposal-tool hard block that prevents new proposals when prior pending items exist
4. Proposal mutation tools:
  - keep proposal creation via existing `propose_*` tools
  - add an update tool for pending proposals, conceptually:
    - `update_pending_proposal(proposal_id, patch_map)`
  - no pending-proposal delete tool in this iteration; pending proposals are resolved via approve/reject
5. Proposal id propagation:
  - all proposal creation/update tools return `proposal_id` (full id + short id helper text)
  - tool outputs and follow-up context should make ids easy for the agent to reuse in later turns
6. Tool-call transparency:
  - persist and expose the exact plain-text tool result that is sent back to the model
  - frontend tool-call expanded view should show:
    - arguments sent by the model
    - model-visible tool result text
    - optional structured JSON payload as secondary debug info

## Planned Implementation Scope

### Backend

- Proposal-tool behavior:
  - remove cross-run pending block in `execute_tool` (`backend/services/agent/tools.py`)
  - extend proposal tool result payloads with proposal ids
- Pending-proposal update tool:
  - add args schema and handler in `backend/services/agent/tools.py`
  - enforce constraints:
    - only `PENDING_REVIEW` items are mutable
    - proposal must belong to the same thread context as the active run
    - patch map validation is change-type aware
- Tool-call persistence/API contract:
  - persist model-visible tool output text in `AgentToolCall`
  - expose it via serializer + API schema + frontend types
  - add migration for any new persistence columns
- Prompt/message-history integration:
  - update review-prefix context formatting in `backend/services/agent/message_history.py` so proposal ids are explicit and reusable
- Tests:
  - remove/replace tests asserting proposal-tool blocking behavior
  - add tests for pending-proposal mutation flow and proposal id return contract
  - add tests for tool output text persistence/serialization

### Frontend

- Review modal action bar (`frontend/src/components/agent/review/AgentRunReviewModal.tsx`):
  - add `Reject All` confirm flow
  - remove `Approve & Next` button and logic
- Diff renderer (`frontend/src/components/agent/review/diff.ts`):
   - add human formatter layer for key fields (currency, amount, selector display)
   - avoid raw JSON-style quoted scalar display for standard fields
   - enforce a friendly entry field order for display and editing previews:
     - `date`, `name`, `kind`, `amount`, `currency`, `from`, `to`, `tags`, `notes`
- Tool-call details (`frontend/src/components/agent/AgentRunBlock.tsx`):
  - show model-visible tool output text in expanded tool call details
  - demote raw JSON to secondary/debug presentation
- Types/API:
  - extend `frontend/src/lib/types.ts` + backend read schema to carry new tool-call text fields

## Affected Files/Modules (Expected)

- Backend:
  - `backend/services/agent/tools.py`
  - `backend/services/agent/runtime.py`
  - `backend/services/agent/message_history.py`
  - `backend/models.py`
  - `backend/schemas.py`
  - `backend/services/agent/serializers.py`
  - `backend/tests/test_agent.py`
  - migration under `alembic/versions/*` (if model schema changes)
- Frontend:
  - `frontend/src/components/agent/review/AgentRunReviewModal.tsx`
  - `frontend/src/components/agent/review/diff.ts`
  - `frontend/src/components/agent/review/diff.test.ts`
  - `frontend/src/components/agent/AgentRunBlock.tsx`
  - `frontend/src/lib/types.ts`
  - agent UI tests under `frontend/src/components/agent/*.test.tsx`

## Operational Impact

- If persistence schema changes are introduced:
  - run migration: `uv run alembic upgrade head`
- Validation commands during implementation:
  - `uv run --extra dev pytest`
  - `cd frontend && npm run test`
  - `cd frontend && npm run build`
  - `uv run python scripts/check_docs_sync.py`

## Constraints and Notes

- Proposal id handling:
  - canonical id remains full id
  - short-hash id may be accepted only when uniquely resolvable
- Pending updates must not mutate already reviewed items (`APPROVED`, `REJECTED`, `APPLIED`, `APPLY_FAILED`).
- `amount_minor` remains source-of-truth for storage; human amount formatting is presentation-only.
- No backward-compatibility shims are required for prototype workflow changes.

## Acceptance Criteria

1. Agent can continue proposing new changes even when prior proposals are still pending review.
2. Agent can update an existing pending proposal via proposal id and field patch map.
3. Proposal tools return reusable proposal ids in tool results.
4. Review modal includes `Reject All` and no longer uses `Approve & Next`.
5. Review diff renders human-friendly values (currency and amount) without raw JSON quoting for standard scalar fields.
6. Entry proposal fields are displayed in the defined friendly order (not alphabetical JSON key order).
7. Tool-call details show the exact model-visible tool output text.
8. Backend and frontend tests are updated to match the new pending-proposal workflow.
9. Docs remain synchronized (`uv run python scripts/check_docs_sync.py` passes).
