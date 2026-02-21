# TODO: Entry Group Graph Workspace (Derived Groups, No First-Class Group CRUD)

## Objective

Add a complete frontend workflow for entry groups where each group is represented as a graph of entries, while preserving the current domain rule that groups are derived from links and are not first-class CRUD resources.

## Current Behavior (as of 2026-02-20)

- Groups are assigned/recomputed in `backend/services/groups.py` as connected components over non-deleted entries and `entry_links`.
- Backend exposes graph read only:
  - `GET /api/v1/groups/{group_id}` returns `GroupGraphRead` (`nodes`, `edges`).
- Frontend shows group graph only on entry detail:
  - `frontend/src/pages/EntryDetailPage.tsx`
  - `frontend/src/components/GroupGraphView.tsx`
- There is no dedicated group workspace page and no direct group CRUD UI.

## Product Constraints (Hard Rules)

1. Groups must remain derived from entry links.
2. Groups must not become first-class CRUD resources.
3. Graph structure (`nodes` + `edges`) is the source-of-truth representation for a group.
4. Group-level user intent maps to link operations:
   - create group shape -> create links
   - update group shape -> add/remove links
   - delete group shape -> remove links until component dissolves
5. Frontend graph rendering should use an existing, well-supported library instead of building a graph visualization system from scratch.

## Scope

### In Scope

- Frontend UX for group-level operations via link management.
- Group discovery/listing and graph-first detail views.
- Clear user guidance that entries persist when links change.

### Out of Scope

- `POST /groups`, `PATCH /groups/{id}`, `DELETE /groups/{id}` endpoints.
- Manual group rename, archived status, or other persistent group metadata.
- Manual assignment of `entry.group_id` from frontend.

## Proposed UX

1. Add a dedicated `Groups` page showing:
   - group list (size, edge count, recent activity)
   - selected group graph visualization
   - member entry table
2. Add link-centric actions from entries and/or group detail:
   - "Connect entries" (creates link)
   - "Remove connection" (deletes link)
3. For destructive graph changes, show impact copy:
   - removing links changes topology and may split a group
   - entries are not deleted
4. Keep group identifiers de-emphasized in UI (avoid exposing raw UUIDs as primary labels).

## Backend/API Work Items

1. Keep existing group graph contract as canonical read model.
2. Add/confirm a group listing read endpoint for frontend discovery (for example `GET /groups` with summary stats) if current entry listing is insufficient.
3. Continue using existing link endpoints for mutations:
   - `POST /entries/{entry_id}/links`
   - `DELETE /links/{link_id}`
4. Preserve recomputation behavior in `recompute_entry_groups` after link changes.
5. Explicitly avoid introducing write endpoints under `/groups`.

## Frontend Work Items

1. Add route and page container:
   - `frontend/src/pages/GroupsPage.tsx` (expected)
2. Add group read-model queries and keys:
   - list groups (if new backend endpoint exists)
   - group graph detail
3. Build group workspace UI:
   - list/table panel
   - graph detail panel
   - member entries panel
4. Add link management controls in group context for create/update/delete intent.
5. Replace or wrap `GroupGraphView` with an established graph UI library (for example React Flow or Cytoscape.js) and avoid custom layout/interaction engine work unless strictly necessary.
6. Start from library defaults and theme/integrate into current UI primitives instead of authoring a bespoke renderer.
7. Add empty/loading/error states consistent with existing pages.

## Affected Files/Modules (Expected)

- Backend:
  - `backend/routers/groups.py`
  - `backend/schemas.py`
  - `backend/services/groups.py`
  - `backend/tests/test_entries.py` and/or new group router tests
- Frontend:
  - `frontend/src/App.tsx` (route registration)
  - `frontend/src/lib/api.ts`
  - `frontend/src/lib/types.ts`
  - `frontend/src/lib/queryKeys.ts`
  - `frontend/src/pages/GroupsPage.tsx` (new)
  - `frontend/src/components/GroupGraphView.tsx`
  - related styling and tests
- Docs:
  - `docs/frontend.md`
  - `docs/backend.md`
  - `docs/api.md`
  - `docs/feature-entry-lifecycle.md`

## Operational Impact

- No migration is expected if group metadata is not introduced.
- Validation during implementation:
  - `uv run --extra dev pytest`
  - `cd frontend && npm run test`
  - `cd frontend && npm run build`
  - `uv run python scripts/check_docs_sync.py`

## Constraints and Known Limitations

1. Group identity is topology-derived; group IDs may change after merges/splits.
2. Library choice should prioritize maintainability (active ecosystem, TypeScript support, pan/zoom, edge labeling, node interaction hooks).
3. Link operations are the only supported mechanism to reshape groups.

## Acceptance Criteria

1. Users can discover existing groups in a dedicated groups workspace.
2. Each group is displayed primarily as a graph (`nodes` and `edges`).
3. Users can perform group-shape CRUD intent through link operations only.
4. No first-class group write endpoints are introduced.
5. Docs and tests are updated and docs-sync check passes.
