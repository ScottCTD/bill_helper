# Feature Map: Entry Lifecycle

This doc is the fast path for understanding how entries are created, edited, linked, grouped, and reviewed.

## Scope

- manual entry CRUD
- entry links/groups
- agent-proposed entry creation

## Contract Summary

- Entry domain fields are defined in `backend/models.py` and `backend/schemas.py`.
- Entry-level `status` is removed from the current model/API.
- Review status exists only on `agent_change_items`.

## Manual Entry Flow

1. UI submit from `frontend/src/components/EntryEditorModal.tsx`.
2. Request via `frontend/src/lib/api.ts` (`createEntry` or `updateEntry`).
3. Router logic in `backend/routers/entries.py`.
4. Tag/entity/user normalization in services:
   - `backend/services/entries.py`
   - `backend/services/entities.py`
   - `backend/services/users.py`
5. Serialization in `backend/services/serializers.py`.
6. Query invalidation in `frontend/src/lib/queryInvalidation.ts`.

## Link/Group Flow

1. Link create/delete via:
   - `POST /entries/{entry_id}/links`
   - `DELETE /links/{link_id}`
2. Group recomputation in `backend/services/groups.py`.
3. Group graph read from `backend/routers/groups.py`.
4. Frontend graph view in `frontend/src/components/GroupGraphView.tsx`.

## Agent-Proposed Entry Flow

1. Agent proposes `create_entry` via `backend/services/agent/tools.py`.
2. Proposal persisted as `agent_change_items` (`PENDING_REVIEW`).
3. Human approves from frontend review UI:
   - `frontend/src/components/agent/review/AgentRunReviewModal.tsx`
4. Apply handler:
   - `backend/services/agent/review.py`
   - `backend/services/agent/change_apply.py`
5. Entry is created directly in `entries` (no entry status field).

## Tests

- `backend/tests/test_entries.py`
- `backend/tests/test_agent.py` (approval/apply entry path)

## Operational Notes

- Currency normalization occurs server-side (`currency_code.upper()`).
- Soft-delete removes entry links and triggers group recomputation.
