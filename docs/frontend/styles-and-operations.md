# Frontend Styles And Operations

## Existing Shared Components

- `EntryEditorModal.tsx`
- `SingleSelect.tsx`
- `CreatableSingleSelect.tsx`
- `TagMultiSelect.tsx`
- `MarkdownBlockEditor.tsx`
- `LinkEditorModal.tsx`
- `GroupGraphView.tsx`
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

- frontend depends on group read-model APIs (`GET /groups`, `GET /groups/{group_id}`)
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
- entry/tag/entity edit-before-approve now uses structured review forms, but delete proposals remain read-only confirmation cards
- `Approve All` and `Reject All` are sequential per-item calls
- entry popup auto-save requires valid required fields
- streaming bubbles render plain text deltas until the final persisted assistant message is refetched
- composer paste and drag-drop accept only images and PDFs
- large bundle warnings can still appear because the editor and charting surfaces are heavy
- taxonomy UI remains flat-list only in V1; there is no delete flow for category terms or parent-term hierarchy editing
