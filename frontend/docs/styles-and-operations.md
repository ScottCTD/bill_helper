# Frontend Styles And Operations

## Existing Shared Components

- `layout/PageHeader.tsx`
- `layout/WorkspaceSection.tsx`
- `layout/WorkspaceToolbar.tsx`
- `layout/StatBlock.tsx`
- `layout/EmptyState.tsx`
- `layout/InlineStatusMessage.tsx`
- `EntryEditorModal.tsx` (entry fields, direct-group picker, and conditional split-role picker)
- `SingleSelect.tsx`
- `CreatableSingleSelect.tsx`
- `TagMultiSelect.tsx`
- `hooks/useFloatingMenuPosition.ts`
- `MarkdownBlockEditor.tsx`
- `GroupGraphView.tsx`
- `GroupEditorModal.tsx`
- `GroupMemberEditorModal.tsx`
- `MetricCard.tsx`
- `ui/MarkdownRenderer.tsx`
- `agent/AgentRunBlock.tsx`
- `agent/activity.ts`
- `agent/review/AgentThreadReviewModal.tsx`
- `agent/review/useAgentThreadReviewController.ts`
- `agent/review/useAgentReviewEditorResources.ts`
- `agent/review/useAgentReviewDraftState.ts`
- `agent/review/ReviewModalHeader.tsx`
- `agent/review/ReviewModalControls.tsx`
- `agent/review/ReviewActiveItemCard.tsx`
- `agent/review/ReviewModalFooter.tsx`
- `agent/review/ReviewEditors.tsx`
- `agent/review/ReviewTocSection.tsx`
- `agent/review/ReviewCatalogEditors.tsx`
- `agent/review/ReviewGroupEditors.tsx`
- `agent/review/modalHelpers.ts`
- `agent/review/drafts/*`
- `agent/review/diff/*`
- `agent/panel/useAgentPanelController.ts`
- `agent/panel/useAgentPanelQueries.ts`
- `agent/panel/useAgentThreadActions.ts`
- `agent/panel/useAgentComposerRuntime.ts`
- `agent/panel/useAgentComposerStreamState.ts`
- `agent/panel/useAgentComposerActions.ts`
- `components/ui/*` for shared primitives

## Feature Modules

- `frontend/src/features/accounts/*`
- `frontend/src/features/properties/*`
- `frontend/src/features/agent/*`
- `frontend/src/features/settings/*`

## Visual Contract

- Bill Helper now uses a compact "ledger workstation" visual system instead of the earlier soft SaaS styling.
- The shared contract is:
  - solid neutral canvas and card surfaces
  - one deep ink-blue primary accent plus restrained semantic tones
  - 8px base radii and stronger borders instead of blur-heavy softness
  - Public Sans for UI/body and JetBrains Mono for code-adjacent metadata
  - tabular numerals enabled by default for ledger and analytic surfaces
- The home route still points to the agent workspace, but it now renders inside the same page header and content shell contract as the rest of the app.

## Styling

- `frontend/src/styles.css` is now only the import/root file.
- Durable style ownership is split across:
  - `frontend/src/styles/tokens.css`
  - `frontend/src/styles/base.css`
  - `frontend/src/styles/shell.css`
  - `frontend/src/styles/workspaces.css`
  - `frontend/src/styles/dashboard.css`
  - `frontend/src/styles/overlays.css`
  - `frontend/src/styles/agent.css`

Key ownership boundaries:

- `tokens.css`: semantic theme variables, chart colors, radii, and elevation tokens
- `base.css`: Tailwind layers, reset styles, global typography, scrollbars, and element defaults
- `shell.css`: app shell, sidebar, content frame, page headers, top-level layout helpers, and the main route scroll container behavior that keeps page widths stable when some routes need vertical scrollbars and others do not while auto-hiding the route scrollbar thumb until active scrolling begins
- `workspaces.css`: shared workspace sections, table/form patterns, settings, entries, properties, and groups
- `dashboard.css`: dashboard controls, timeline rail, comparison cards, and dashboard-only layout
- `overlays.css`: entry editor, select/tag controls, tooltip, and notification surfaces
- BlockNote-based markdown editor shells inherit the app card surface, so the full editor frame stays on one white panel instead of exposing the muted page canvas below the editable content
- custom select/tag menus render in a floating portal anchored by `hooks/useFloatingMenuPosition.ts`, so short cards, empty states, and other clipped containers do not truncate the menu body
- `agent.css`: agent panel, thread rail, timeline, composer, and review modal styling

## Design System And Config

- Tailwind config: `frontend/tailwind.config.ts`
- PostCSS config: `frontend/postcss.config.js`
- shadcn manifest: `frontend/components.json`
- utility merge helper: `frontend/src/lib/utils.ts`
- font loading entrypoint: `frontend/index.html`

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
- page-level integration tests cover accounts, properties, and settings orchestration flows
- taxonomy term changes invalidate taxonomy-term usage caches
- install, test, and build commands remain:
  - `npm install`
  - `npm run test`
  - `npm run build`

## Constraints And Known Limitations

- no pagination controls in the agent thread or timeline UI yet
- thread review is the only review entry point; per-run timeline cards do not expose their own review CTA
- entry/tag/entity/group edit-before-approve now uses structured review forms, while delete-group and delete-member proposals remain read-only confirmation cards
- group add-member review shows the parent group by name and renders entry members as locked full-entry forms; split role stays editable, and pending create-proposal refs remain locked behind dependency chips
- `Approve All` and `Reject All` are sequential per-item calls
- entry popup auto-save requires valid required fields
- entry popup can assign at most one direct group; broader group topology remains managed in the groups workspace
- group edges are derived only; the UI does not provide manual edge editing
- child-group nesting is limited to one level by the backend contract
- streaming bubbles render plain text deltas until the final persisted assistant message is refetched
- composer paste and drag-drop accept only images and PDFs
- large bundle warnings can still appear because the editor and charting surfaces are heavy
- taxonomy UI remains flat-list only in V1; there is no delete flow for category terms or parent-term hierarchy editing
