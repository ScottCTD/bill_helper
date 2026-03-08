# Frontend Agent Workspace

## Main Coordinator

- `frontend/src/features/agent/AgentPanel.tsx`
- used as the primary AI page via `frontend/src/pages/HomePage.tsx`
- stateful coordination stays in `AgentPanel`, while rendering and derivation are split into feature-owned modules

Supporting modules include:

- `frontend/src/features/agent/AgentRunBlock.tsx`
- `frontend/src/features/agent/activity.ts`
- `frontend/src/features/agent/panel/AgentThreadList.tsx`
- `frontend/src/features/agent/panel/AgentThreadPanel.tsx`
- `frontend/src/features/agent/panel/AgentTimeline.tsx`
- `frontend/src/features/agent/panel/AgentComposer.tsx`
- `frontend/src/features/agent/panel/AgentThreadUsageBar.tsx`
- `frontend/src/features/agent/panel/AgentAttachmentPreviewDialog.tsx`
- `frontend/src/features/agent/panel/useAgentDraftAttachments.ts`
- `frontend/src/features/agent/panel/useStickToBottom.ts`
- `frontend/src/hooks/useResizablePanel.ts`
- `frontend/src/features/agent/review/AgentThreadReviewModal.tsx`
- `frontend/src/features/agent/review/drafts.ts`
- `frontend/src/features/agent/review/model.ts`
- `frontend/src/features/agent/review/diff.ts`

## Timeline Behavior

- thread rail is on the right, collapsible, resizable, and independently scrollable
- thread rows expose hover/focus delete controls, support double-click inline rename, and reconcile multiple optimistic running ids with persisted `has_running_run`
- timeline is event-driven from persisted `run.events`
- tool rows appear as queued, then update in place through running, completed, failed, or cancelled
- live SSE `run_event` payloads can include a compact `tool_call` snapshot so tool rows show their real name before full hydration
- streamed `rename_thread` calls hydrate immediately so the thread rail relabels before the assistant finishes the turn
- live SSE `reasoning_delta` and `text_delta` chunks render transient Reasoning and Assistant updates inside the same activity bubble until persisted events/messages reconcile
- compact tool-call snapshots are hydrated on demand from `GET /agent/tool-calls/{tool_call_id}`
- assistant activity and transient SSE text render in the same assistant/update bubble
- optimistic user and assistant placeholders reconcile against persisted timeline messages

## Thread Review Surface

- review actions are handled in `frontend/src/features/agent/review/AgentThreadReviewModal.tsx`
- the header `Review` button is the only review entry point and opens one thread-scoped dialog for all proposal items across the selected thread
- the dialog uses responsive width rules, lets reviewers collapse the left TOC, groups TOC rows by proposal domain (`Entries`, `Groups`, `Entities`, `Tags`) within `Pending` and `Reviewed / Failed`, and surfaces batch plus per-item review controls in a full-width bar above the denser review surface
- proposals render CRUD-aware field-level diffs, and reviewer overrides update the preview for create and update entry/tag/entity/group proposals plus add-member group proposals
- entry create/update review uses the same field model as `EntryEditorModal` through `frontend/src/features/agent/review/drafts.ts`; tag review edits only `name` and `type`, entity review edits only `name` and `category`, create/update group review edits `name` plus create-only `group_type`
- create-group-member review shows the resolved parent group name plus a read-only full entry snapshot for entry members; the only editable field in v1 is split role, and the diff preview treats membership changes as a group assignment update so only the `group` field (and split role when relevant) changes instead of re-highlighting the whole entry payload
- proposal-backed group or entry dependencies show chips only while the referenced create proposal is still unresolved; once that dependency is `APPLIED`, the review surface falls back to the resolved group name and entry snapshot without a dependency banner
- delete-group and delete-group-member proposals stay confirmation-only in v1
- non-applied items remain reviewer-editable after rejection or apply failure, so reviewers can revise the payload, move it back to `PENDING_REVIEW`, or approve it directly from the reviewed section; `APPLIED` items stay read-only
- `Approve All` and `Reject All` remain sequential per-item API workflows and reuse any saved reviewer drafts
- pending TOC rows rely on the section grouping instead of repeating a `PENDING_REVIEW` status badge, while resolved rows use compact symbolic status chips for audit context
- apply failures surface inline on the affected item; local editor validation stays client-side and does not synthesize `APPLY_FAILED`

## Composer

- pinned composer surface with attachment chips and preview dialog
- supports picker, paste, and drag-drop for images and PDFs
- includes a `Bulk mode` toggle beside `Add Attachments`
- Bulk mode creates one fresh thread per attached file, reuses the current textarea prompt for every launch, and never copies the currently selected thread history
- Bulk launch concurrency uses the resolved runtime setting `agent_bulk_max_concurrent_threads` and falls back to `4` until settings load
- Bulk mode help is exposed through a hover/focus tooltip beside the toggle instead of persistent helper text
- Bulk launches report transient started/failed toast notifications; failed files stay attached for retry while successful files clear
- `Cmd/Ctrl+Enter` always submits; plain `Enter` submits only for a single-line draft
- idle primary action is `Send`; active-run primary action is `Stop`
- when Bulk mode is enabled, the primary action becomes `Start Bulk` and uses the existing non-stream send endpoint per created thread
- agent messages stream over SSE from `POST /api/v1/agent/threads/{thread_id}/messages/stream`

## Usage And Activity

- cumulative usage bar shows `Context`, `Total input`, `Output`, `Cache read`, `Cache hit rate`, and total cost
- `Context` comes from backend persisted run snapshots
- live activity is driven by `run_event`; usage totals remain query-time read models rather than incremental SSE counters
- run summary cards count pending change types across entries, groups, tags, and entities
