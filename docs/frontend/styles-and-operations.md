# Frontend Styles And Operations

## Existing Shared Components

- `EntryEditorModal.tsx` (entry fields, direct-group picker, and conditional split-role picker)
- `SingleSelect.tsx`
- `CreatableSingleSelect.tsx`
- `TagMultiSelect.tsx`
- `MarkdownBlockEditor.tsx`
- `GroupGraphView.tsx`
- `GroupEditorModal.tsx`
- `GroupMemberEditorModal.tsx`
- `MetricCard.tsx`
- `ui/MarkdownRenderer.tsx`
- `agent/AgentRunBlock.tsx`
- `agent/activity.ts`
- `agent/review/AgentThreadReviewModal.tsx`
- `agent/review/drafts.ts`
- `agent/review/diff.ts`
- `components/ui/*` for shared primitives

## Feature Modules

- `frontend/src/features/accounts/*`
- `frontend/src/features/properties/*`
- `frontend/src/features/agent/*`

## Styling (`frontend/src/styles.css`)

Includes:

- Tailwind base, components, and utilities imports
- CSS variable token layer
- shared table surface classes
- properties workspace classes
- entries secondary-name line classes
- dialog and form layout classes
- dashboard tab classes
- agent timeline and header styling
- tokenized scrollbar styling and stable scrollbar gutters

## Design System And Config

- Tailwind config: `frontend/tailwind.config.ts`
- PostCSS config: `frontend/postcss.config.js`
- shadcn manifest: `frontend/components.json`
- utility merge helper: `frontend/src/lib/utils.ts`

## Operational Impact

- frontend depends on entry group-context fields (`direct_group`, `group_path`) in entry read models
- frontend also depends on entry read/write support for `direct_group_member_role` when editing split-group membership from the entry modal
- frontend depends on group CRUD and graph APIs:
  - `POST /groups`
  - `GET /groups`
  - `GET /groups/{group_id}`
  - `PATCH /groups/{group_id}`
  - `DELETE /groups/{group_id}`
  - `POST /groups/{group_id}/members`
  - `DELETE /groups/{group_id}/members/{membership_id}`
- agent send depends on SSE parsing for `text_delta` and persisted `run_event`
- query keys and invalidation logic are centralized and should be reused
- page-level integration tests cover accounts and properties orchestration flows
- taxonomy term changes invalidate taxonomy-term usage caches
- install, test, and build commands remain:
  - `npm install`
  - `npm run test`
  - `npm run build`

## Constraints And Known Limitations

- no pagination controls in the agent thread or timeline UI yet
- thread review is the only review entry point; per-run timeline cards do not expose their own review CTA
- entry/tag/entity/group edit-before-approve now uses structured review forms, while delete-group and delete-member proposals remain read-only confirmation cards
- group add-member review can edit existing resource refs, but pending create-proposal refs stay locked behind dependency chips
- `Approve All` and `Reject All` are sequential per-item calls
- entry popup auto-save requires valid required fields
- entry popup can assign at most one direct group; broader group topology remains managed in the groups workspace
- group edges are derived only; the UI does not provide manual edge editing
- child-group nesting is limited to one level by the backend contract
- streaming bubbles render plain text deltas until the final persisted assistant message is refetched
- composer paste and drag-drop accept only images and PDFs
- large bundle warnings can still appear because the editor and charting surfaces are heavy
- taxonomy UI remains flat-list only in V1; there is no delete flow for category terms or parent-term hierarchy editing
