# Feature Map: Entry Lifecycle

This doc is the fast path for understanding how entries are created, edited, linked, grouped, and reviewed.

## Scope

- manual entry CRUD
- entry links/groups
- agent-proposed entry CRUD (review-gated)

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
3. Group read models from `backend/routers/groups.py`:
   - `GET /groups` for derived linked-group summaries (`entry_count >= 2`)
   - `GET /groups/{group_id}` for graph detail
4. Frontend group workspace and graph view:
   - `frontend/src/pages/GroupsPage.tsx`
   - `frontend/src/components/LinkEditorModal.tsx` for modal link creation from `+` actions
   - `frontend/src/components/GroupGraphView.tsx` (React Flow renderer)
   - `GroupGraphView.tsx` filters React Flow dev warning `002` locally because that warning is a false positive for this view; other graph warnings still surface
5. Group-shape CRUD intent is link-driven only (no first-class group CRUD endpoints).

## Agent-Proposed Entry Flow

1. Agent proposes `create_entry` / `update_entry` / `delete_entry` via the split tool stack:
   `backend/services/agent/tool_handlers_propose.py` + `backend/services/agent/tool_runtime.py`
   (re-exported through `backend/services/agent/tools.py`).
2. Proposal persisted as `agent_change_items` (`PENDING_REVIEW`).
3. Human approves from frontend review UI:
   - `frontend/src/features/agent/review/AgentRunReviewModal.tsx`
4. Apply handler:
   - `backend/services/agent/review.py`
   - `backend/services/agent/change_apply.py`
5. Apply handler resolves target by selector for update/delete:
   - `date + amount_minor + from_entity + to_entity + name`
6. Entry mutation is applied directly to `entries` (no entry status field).

## Tests

- `backend/tests/test_entries.py`
- `backend/tests/test_agent.py` (approval/apply entry path)

## Operational Notes

- Currency normalization occurs server-side (`currency_code.upper()`).
- Agent create-entry proposals can omit `currency_code`; backend defaults to resolved runtime default currency (`/settings` override, else `BILL_HELPER_DEFAULT_CURRENCY_CODE`).
- Soft-delete removes entry links and triggers full active-entry group recomputation (connected components are rebuilt across all non-deleted entries).
- Entries list date cells are rendered as no-wrap with a compact fixed width so `YYYY-MM-DD` values stay on one line.
- Entries list name cells now render a compact secondary `from -> to` line under the primary name; long entity names are trimmed per side in `frontend/src/pages/EntriesPage.tsx` and styled by the `.entries-name-*` classes in `frontend/src/styles.css`.
