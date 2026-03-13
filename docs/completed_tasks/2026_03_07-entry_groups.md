# Entry Groups v2

Status: implemented and verified locally on 2026-03-07. This task doc is archived under `docs/completed_tasks/`.

## Implemented Scope

- Replaced the old link-derived connected-component model with first-class named groups.
- Added typed groups: `BUNDLE`, `SPLIT`, and `RECURRING`.
- Added direct membership through `entry_group_members`, supporting entries and one-level child groups.
- Removed active runtime use of `entry_links` and removed `entries.group_id` from the live schema/API.
- Kept explicit edge storage out of scope; `GET /groups/{id}` derives nodes and edges from group type plus direct membership.

## Backend Changes

- `EntryGroup` now stores `owner_user_id`, `name`, and `group_type`.
- `EntryGroupMember` now stores direct membership with either `entry_id` or `child_group_id`, optional `member_role`, and deterministic ordering fields.
- `backend/services/groups.py` now owns:
  - group CRUD
  - direct membership mutation
  - depth-1 nesting and no-sharing validation
  - derived graph generation
- Group rules now enforced:
  - `BUNDLE`: fully connected graph over direct members
  - `SPLIT`: at most one `PARENT`; parent descendants must be `EXPENSE`, children descendants must be `INCOME`
  - `RECURRING`: all descendant entries must share one `EntryKind`; edges form a chronological chain
- Agent entry creation/update paths no longer assign or recompute group ids; entries remain ungrouped until added to a group.

## Migration

- Added `alembic/versions/0026_entry_groups_v2.py`.
- Legacy multi-entry linked components migrate into top-level typed groups when possible:
  - valid split-shaped components migrate to `SPLIT`
  - valid recurring-shaped components migrate to `RECURRING`
  - mixed or invalid legacy components fall back to `BUNDLE`
- Singleton legacy groups are not recreated as first-class groups.

## Frontend Changes

- Replaced link creation/deletion UX with group creation, rename, delete, add-member, and remove-member flows.
- `frontend/src/pages/GroupsPage.tsx` now manages first-class groups and direct membership.
- `frontend/src/pages/EntryDetailPage.tsx` now shows `direct_group`, `group_path`, and the direct-group graph instead of raw links.
- `frontend/src/components/EntryEditorModal.tsx` now allows assigning one direct group inline from entry create/edit; `SPLIT` groups also expose a split-role picker there.
- `frontend/src/components/GroupGraphView.tsx` now renders discriminated entry and child-group nodes with layout variants for `BUNDLE`, `SPLIT`, and `RECURRING`.
- Added:
  - `frontend/src/components/GroupEditorModal.tsx`
  - `frontend/src/components/GroupMemberEditorModal.tsx`
- Removed:
  - `backend/routers/links.py`
  - `frontend/src/components/LinkEditorModal.tsx`

## API Surface

- `POST /groups`
- `GET /groups`
- `GET /groups/{group_id}`
- `PATCH /groups/{group_id}`
- `DELETE /groups/{group_id}`
- `POST /groups/{group_id}/members`
- `DELETE /groups/{group_id}/members/{membership_id}`

Entry contracts now expose:

- `direct_group`
- `group_path`

Entry detail no longer exposes:

- `links`
- derived `group_id`

## Verification Completed

- `uv run --extra dev python -m py_compile backend/enums_finance.py backend/models_finance.py backend/schemas_finance.py backend/services/serializers.py backend/services/access_scope.py backend/services/entries.py backend/services/groups.py backend/routers/entries.py backend/routers/groups.py backend/services/agent/change_apply.py backend/main.py`
- `uv run --extra dev pytest backend/tests/test_entries.py backend/tests/test_migrations_core.py -q`
- `OPENROUTER_API_KEY=test uv run --extra dev pytest backend/tests -q`
- `npm test`
- `npm run build`
- `uv run python scripts/check_docs_sync.py`

## Follow-Up Decision

- Archived at `docs/completed_tasks/2026_03_07-entry_groups.md` after implementation and verification.
