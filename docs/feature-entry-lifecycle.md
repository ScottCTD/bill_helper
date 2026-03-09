# Feature Map: Entry Lifecycle

This doc is the fast path for understanding how entries are created, edited, grouped, and reviewed.

## Scope

- manual entry CRUD
- entry groups
- agent-proposed entry CRUD (review-gated)

## Contract Summary

- Entry domain fields are defined in `backend/models.py` and `backend/schemas.py`.
- Entry-level `status` is removed from the current model/API.
- Review status exists only on `agent_change_items`.
- Entry read models expose group context through `direct_group` and `group_path`.

## Manual Entry Flow

1. UI submit from `frontend/src/components/EntryEditorModal.tsx`.
2. Optional direct-group assignment is chosen in the same modal. `SPLIT` targets also require a split role.
3. Request via `frontend/src/lib/api.ts` (`createEntry` or `updateEntry`).
4. HTTP boundary in `backend/routers/entries.py` parses request models and maps service policy failures to HTTP responses.
5. Typed entry workflow orchestration in `backend/services/entries.py`:
   - entry create/update commands
   - principal-scoped account/user/group loading
   - tag/entity/user normalization
   - direct-group membership assignment and validation
6. Supporting service helpers:
   - `backend/services/entities.py`
   - `backend/services/users.py`
   - `backend/services/groups.py` for direct-group membership assignment/validation
7. Serialization in `backend/services/serializers.py`.
8. Query invalidation in `frontend/src/lib/queryInvalidation.ts`.

## Group Flow

1. Group create, rename, delete, and membership edits come from:
   - `frontend/src/pages/GroupsPage.tsx`
   - `frontend/src/components/GroupDetailModal.tsx`
   - `frontend/src/components/GroupEditorModal.tsx`
   - `frontend/src/components/GroupMemberEditorModal.tsx`
2. Requests go through:
   - `POST /groups`
   - `PATCH /groups/{group_id}`
   - `DELETE /groups/{group_id}`
   - `POST /groups/{group_id}/members`
   - `DELETE /groups/{group_id}/members/{membership_id}`
3. Group validation and graph derivation live in `backend/services/groups.py`.
4. Group read models from `backend/routers/groups.py`:
   - `GET /groups` for named group summaries
   - `GET /groups/{group_id}` for direct-member graph detail
5. Entry detail uses the same graph read model when `direct_group` is present:
   - `frontend/src/pages/EntryDetailPage.tsx`
   - `frontend/src/components/GroupGraphView.tsx`
6. Entry create/edit modal can assign one direct group without leaving the entry workflow; the dedicated groups workspace remains the place for broader structural edits and child-group management, now through a table-first group browser plus detail modal with direct-entry stats and a bottom-anchored graph section.
7. No manual edge editing exists in v1; users edit direct membership and split roles only.

## Agent-Proposed Entry Flow

1. Agent proposes `create_entry` / `update_entry` / `delete_entry` via the split tool stack:
   `backend/services/agent/tool_handlers_propose.py` + `backend/services/agent/tool_runtime.py`
   (re-exported through `backend/services/agent/tools.py`).
2. Proposal persisted as `agent_change_items` (`PENDING_REVIEW`).
3. Human reviews from the thread-scoped frontend review UI opened by the agent header `Review` button:
   - `frontend/src/features/agent/review/AgentThreadReviewModal.tsx`
   - `frontend/src/features/agent/review/drafts.ts`
4. Apply handler:
   - `backend/services/agent/review.py`
   - `backend/services/agent/change_apply.py`
5. Apply handler resolves target by selector for update/delete:
   - `date + amount_minor + from_entity + to_entity + name`
6. Entry mutation is applied directly to `entries` (no entry status field); agent-created entries remain ungrouped until a user assigns them to a group.

## Tests

- `backend/tests/test_entries.py`
- `backend/tests/test_entries_service.py`
- `backend/tests/test_agent.py` (approval/apply entry path)
- `backend/tests/test_migrations_core.py`

## Operational Notes

- Currency normalization occurs server-side (`currency_code.upper()`).
- Agent create-entry proposals can omit `currency_code`; backend defaults to resolved runtime default currency (`/settings` override, else `BILL_HELPER_DEFAULT_CURRENCY_CODE`).
- Thread review aggregates proposals across all runs in the selected thread; pending items are reviewed first while applied, rejected, and failed items remain visible for audit.
- Reviewer edit-before-approve uses structured entry/tag/entity forms and serializes any approved edits back through `payload_override`.
- Soft-delete removes direct group membership for the deleted entry.
- Empty groups are allowed so users can create a group shell before adding members.
- Group nesting depth is limited to one. Child groups cannot be shared across multiple parents.
- `SPLIT` groups require member roles and validate descendant entry kinds; `RECURRING` groups validate same-kind descendants and derive a chronological chain from representative dates.
- `GroupGraphView.tsx` filters React Flow dev warning `002` locally because that warning is a false positive for this view; other graph warnings still surface.
- Entries list date cells are rendered as no-wrap with a compact fixed width so `YYYY-MM-DD` values stay on one line.
- Entries list name cells now render a compact secondary `from -> to` line under the primary name; long entity names are trimmed per side in `frontend/src/pages/EntriesPage.tsx` and styled by the `.entries-name-*` classes in `frontend/src/styles.css`.
