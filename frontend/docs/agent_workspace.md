# Frontend Agent Workspace

## Main Coordinator

- `frontend/src/features/agent/AgentPanel.tsx`
- used as the primary AI page via `frontend/src/pages/HomePage.tsx`
- the home route now adds the shared `PageHeader` plus the shared outer workspace card shell above the agent panel so the AI workspace sits inside the same route-level shell contract as the ledger pages
- acts as a render shell that wires the header, timeline, composer, thread rail, review modal, and delete confirmation together
- stateful coordination now lives in `frontend/src/features/agent/panel/useAgentPanelController.ts`, which composes `useAgentPanelQueries.ts` for thread/runtime queries, `useAgentThreadActions.ts` for thread/review mutations plus cache helpers, and `useAgentComposerRuntime.ts` for composer/panel coordination; stream hydration/state lives in `useAgentComposerStreamState.ts`, send-stop orchestration lives in `useAgentComposerActions.ts`, and pure panel helpers live in `frontend/src/features/agent/panel/helpers.ts`
- the header **New Thread** control clears selection into a client-only draft (no `POST /agent/threads`); the first outbound send calls `ensureThreadId()` in `useAgentComposerActions.ts`, which creates the server thread and selects it; `useAgentPanelQueries.ts` skips auto-selecting the newest/first listed thread while that draft is active so the rail does not snap back
- page header uses the static title `Bill Assistant`; model selection stays in the composer dropdown instead of the title row
- visual styling now follows the same compact neutral workspace system as the rest of the app: the agent panel is no longer a full-screen bespoke surface with separate page chrome
- the route-level border now comes from the same shared workspace shell used by the ledger pages; the agent panel renders borderless inside that shell
- the main conversation column stays width-capped for readability and centered within the shared workspace panel

Supporting modules include:

- `frontend/src/features/agent/panel/useAgentPanelController.ts`
- `frontend/src/features/agent/panel/useAgentPanelQueries.ts`
- `frontend/src/features/agent/panel/useAgentThreadActions.ts`
- `frontend/src/features/agent/panel/useAgentComposerRuntime.ts`
- `frontend/src/features/agent/panel/useAgentComposerStreamState.ts`
- `frontend/src/features/agent/panel/useAgentComposerActions.ts`
- `frontend/src/features/agent/panel/helpers.ts`
- `frontend/src/features/agent/AgentRunBlock.tsx`
- `frontend/src/features/agent/AgentRunActivity.tsx`
- `frontend/src/features/agent/AssistantMessageRunWork.tsx`
- `frontend/src/features/agent/activity.ts`
- `frontend/src/features/agent/panel/AgentThreadList.tsx`
- `frontend/src/features/agent/panel/AgentThreadPanel.tsx`
- `frontend/src/features/agent/panel/AgentTimeline.tsx`
- `frontend/src/features/agent/panel/AgentComposer.tsx`
- `frontend/src/features/agent/panel/AgentThreadUsageBar.tsx`
- `frontend/src/features/agent/panel/useAgentDraftAttachments.ts`
- `frontend/src/features/agent/panel/AgentMessageAttachmentImage.tsx`
- `frontend/src/features/agent/panel/useStickToBottom.ts`
- `frontend/src/hooks/useResizablePanel.ts`
- `frontend/src/features/agent/review/AgentThreadReviewModal.tsx`
- `frontend/src/features/agent/review/ReviewModalHeader.tsx`
- `frontend/src/features/agent/review/ReviewModalControls.tsx`
- `frontend/src/features/agent/review/ReviewActiveItemCard.tsx`
- `frontend/src/features/agent/review/ReviewModalFooter.tsx`
- `frontend/src/features/agent/review/useAgentThreadReviewController.ts`
- `frontend/src/features/agent/review/useAgentReviewEditorResources.ts`
- `frontend/src/features/agent/review/useAgentReviewDraftState.ts`
- `frontend/src/features/agent/review/ReviewEditors.tsx`
- `frontend/src/features/agent/review/ReviewTocSection.tsx`
- `frontend/src/features/agent/review/ReviewCatalogEditors.tsx`
- `frontend/src/features/agent/review/ReviewGroupEditors.tsx`
- `frontend/src/features/agent/review/modalHelpers.ts`
- `frontend/src/features/agent/review/drafts/*`
- `frontend/src/features/agent/review/model.ts`
- `frontend/src/features/agent/review/diff/*`

## Timeline Behavior

- thread rail is on the right, collapsible, resizable, and independently scrollable
- thread rail now reads as a secondary navigation panel inside the shared workspace instead of a floating side app
- thread rows expose hover/focus delete controls, route deletion through the shared in-app confirmation dialog instead of a browser-native alert, support double-click inline rename with a visible active single-line field that preserves native selection and horizontal scrolling for long titles, render the full normalized title text before CSS truncation, and reuse one trailing action slot so hover/focus swaps delete in over the running spinner instead of reserving separate dead space
- running state is thread-scoped rather than panel-global, so a background stream keeps its spinner in the rail without forcing other selected idle threads into a stop-oriented composer state
- delete stays unavailable only for the specific running or deleting thread; idle sibling threads keep their delete affordance even while another thread is active
- inline rename remains available per thread unless that same thread already has a rename mutation in flight
- assistant turns and user bubbles share the same centered readable column; assistant content drops the outer bubble shell, while user bubbles stay right-aligned within that column and only go edge-to-edge when the panel is narrow
- timeline is event-driven from persisted `run.events`
- tool rows appear as queued, then update in place through running, completed, failed, or cancelled
- backend tool-call payloads now include a high-signal `display_label`; the timeline uses that summary for both compact SSE snapshots and hydrated rows instead of rendering raw tool names
- streamed `rename_thread` calls hydrate immediately so the thread rail relabels before the assistant finishes the turn
- reasoning updates and interleaved assistant text render as plain markdown at `text-xs` / `font-medium` / foreground in the same **Public Sans** UI stack as the rest of the app (smaller than the final `text-sm` reply); tool-call rows use `font-normal` / muted labels, no chevron—click the row to expand details; live SSE `reasoning_delta` feeds that list, while `text_delta` streams the main assistant answer as normal markdown below the activity list in the same turn
- completed turns collapse that activity behind a centered separator (work duration plus tool/update counts); clicking the separator expands the full timeline above it; the persisted assistant message body remains the primary visible reply when collapsed
- compact tool-call snapshots are hydrated on demand from `GET /agent/tool-calls/{tool_call_id}`
- manually expanding or collapsing activity/tool-call details detaches the timeline from auto-follow so the clicked location stays stable until the reviewer scrolls back to bottom
- optimistic user and assistant placeholders reconcile against persisted timeline messages; when the assistant placeholder is replaced by a persisted row while the run is still active, `text_delta` / `reasoning_delta` buffers stay live so the same turn keeps streaming on that message (buffers clear when the stream finishes or the run stops)
- persisted image attachments render through authenticated blob fetches so previews survive thread reloads even though the API uses bearer-token auth instead of cookie-backed file URLs
- user-message attachments render as compact file rows above the message text and open in a browser-native tab instead of embedding inline previews inside the bubble
- composer pending attachments, user attachment rows, and assistant inline attachment grids each cap height with internal vertical scroll when the list is long (`scroll-surface` plus classes in `frontend/src/styles/agent.css`) so the composer and bubbles do not grow unbounded and the scrollbar matches the app’s styled scrollbars; those strips share a bordered, muted background “tray” with tighter gaps and padding than the main bubble chrome
- assistant-message inline attachment cards stay bounded: images preserve their aspect ratio up to a larger capped size and open in a browser-native tab when clicked, while PDFs use a small scrollable browser preview plus filename label and an explicit `Open` action
- `useAgentComposerStreamState.ts` owns stream-event accumulation, tool-call hydration, rename-thread reconciliation, and the optimistic run timeline cache

## Thread Review Surface

- review actions are coordinated by `frontend/src/features/agent/review/useAgentThreadReviewController.ts`, while `AgentThreadReviewModal.tsx` now stays focused on dialog shell/layout composition
- `useAgentThreadReviewController.ts` now stays on item navigation plus review actions, while `useAgentReviewEditorResources.ts` owns catalog/settings queries and `useAgentReviewDraftState.ts` owns reviewer draft maps plus payload-override shaping
- review modal presentation is split across `ReviewModalHeader.tsx`, `ReviewModalControls.tsx`, `ReviewActiveItemCard.tsx`, and `ReviewModalFooter.tsx` so card rendering, action chrome, and footer messaging do not regrow inside the modal shell
- the header `Review` button is the only review entry point and opens one thread-scoped dialog for all proposal items across the selected thread
- the dialog uses responsive width rules, lets reviewers collapse the left TOC, groups TOC rows in dependency-friendly order (`Accounts`, `Snapshots`, `Entities`, `Tags`, `Groups`, `Entries`, `Group members`) within `Pending` and `Reviewed / Failed`, sorts the flat proposal list the same way for navigation and batch actions, and surfaces batch plus per-item review controls in a full-width bar above the denser review surface
- the review modal now follows the same compact border-first styling as the rest of the app instead of relying on pill-heavy special-case chrome
- proposals render CRUD-aware field-level diffs, and reviewer overrides update the preview for create and update entry/account/tag/entity/group proposals plus add-member group proposals
- `ReviewEditors.tsx` is now the stable export seam; `ReviewTocSection.tsx` owns TOC navigation, `ReviewCatalogEditors.tsx` owns entry/account/entity/tag editors, `ReviewGroupEditors.tsx` owns group and membership editors plus dependency chips, and reusable selection/status helpers live in `frontend/src/features/agent/review/modalHelpers.ts`
- draft normalization and override builders now live in `frontend/src/features/agent/review/drafts/`, split across shared coercion helpers plus `entries`, `catalog`, and `memberships` ownership modules
- entry create/update review uses the same field model as `EntryEditorModal` through `frontend/src/features/agent/review/drafts/entries.ts`, including the ranked fuzzy tag picker; account review edits `name`, `currency`, `active`, and `notes`; tag review edits only `name` and `type`; entity review edits only `name` and `category`; create/update group review edits `name` plus create-only `group_type`
- create-group-member review shows the resolved parent group name plus a read-only full entry snapshot for entry members; the only editable field in v1 is split role, and the diff preview treats membership changes as a group assignment update so only the `group` field (and split role when relevant) changes instead of re-highlighting the whole entry payload
- diff rendering and record-shaping helpers now live in `frontend/src/features/agent/review/diff/`, split between reusable diff primitives in `core.ts` and proposal-family record builders in `domains.ts`
- proposal-backed group or entry dependencies show chips only while the referenced create proposal is still unresolved; once that dependency is `APPLIED`, the review surface falls back to the resolved group name and entry snapshot without a dependency banner
- delete-group and delete-group-member proposals stay confirmation-only in v1
- non-applied items remain reviewer-editable after rejection or apply failure, so reviewers can revise the payload, move it back to `PENDING_REVIEW`, or approve it directly from the reviewed section; `APPLIED` items stay read-only
- `Approve All` and `Reject All` remain sequential per-item API workflows and reuse any saved reviewer drafts
- pending TOC rows rely on the section grouping instead of repeating a `PENDING_REVIEW` status badge, while resolved rows use compact symbolic status chips for audit context
- apply failures surface inline on the affected item; local editor validation stays client-side and does not synthesize `APPLY_FAILED`

## Composer

- pinned composer surface with stacked attachment prep cards; the bottom control row is compact (icon-first attach, short Bulk label, model and approval-policy selects, send/stop)
- composer now stays docked against the bottom edge of the agent workspace instead of leaving dead space below the input row
- textarea and control row share one card surface instead of reading as separate color bands
- supports picker, paste, and drag-drop for images and PDFs
- composer attachments upload immediately on selection, then continue through server-side preparation before send; each draft card stays on one line with the filename, a live status label, and a compact inline progress bar beside the filename
- composer draft attachments stay removable while they are uploading or otherwise preparing so the user can drop a file before sending
- single-send and Bulk mode both wait for all draft attachments to finish upload/parsing before the actual message request starts; once ready, the send request references persisted `attachment_ids` instead of re-uploading the same files
- when attachments are present, the composer shows an `OCR` toggle beside `Bulk mode`; vision-capable models default it off for new attachments, while non-vision models keep it checked and disabled
- draft status labels map directly to the active preparation mode: `Parsing…` means OCR/Docling is still running, `Preparing pages…` means a PDF is being converted into page images without OCR text, `Saving…` means a non-OCR image upload is finishing server-side, and `Ready` means the persisted draft attachment can be sent immediately
- flipping `OCR` off while an OCR-backed draft is still uploading/parsing aborts that in-flight draft and restarts it in non-OCR preparation mode so the composer stops waiting on OCR work
- flipping `OCR` on while a non-OCR draft is still preparing restarts that draft in OCR mode so the composer waits for `Parsing…` before send
- message attachments use browser-native large-view behavior instead of an app modal: user-message attachments stay compact file rows, assistant images open in a native tab on click, and assistant PDFs expose an `Open` action beside the inline preview
- includes a `Bulk` toggle beside `Attach` (file picker)
- shows an **Approval policy** select (`Default` vs `Yolo`) next to the model picker; `Default` keeps the existing review workflow, `Yolo` sends `approval_policy=yolo` on the next message so the backend auto-applies this run’s pending proposals after a successful completion (same dependency rules as manual approval)
- shows an `Agent model` dropdown beside the policy control and sources options from runtime settings `available_agent_models` in the same order; option text uses `agent_model_display_names` when set, otherwise the raw model id
- initializes the picker from the latest run model when a thread has history, otherwise falls back through the thread's configured model and runtime default `agent_model`
- changing the picker only affects the next `POST /api/v1/agent/threads/{thread_id}/messages` or `/messages/stream` request; existing thread history is still sent unchanged
- Bulk mode creates one fresh thread per attached file, reuses the current textarea prompt for every launch, and never copies the currently selected thread history
- Bulk launch concurrency uses the resolved runtime setting `agent_bulk_max_concurrent_threads` and falls back to `4` until settings load
- Bulk mode help is exposed through a hover/focus tooltip beside the toggle instead of persistent helper text
- Bulk launches report transient started/failed toast notifications; failed files stay attached for retry while successful files clear
- `Cmd/Ctrl+Enter` always submits; plain `Enter` submits only for a single-line draft
- idle primary action is `Send`; active-run primary action is `Stop`
- switching to an idle thread restores that thread's own composer state immediately, even if another thread continues streaming in the background
- stop actions are selected-thread scoped: the composer only shows `Stop` when the selected thread itself is running, and interrupt requests target that selected thread's current run only
- when Bulk mode is enabled, the primary action becomes `Start Bulk` and uses the existing non-stream send endpoint per created thread
- agent messages stream over SSE from `POST /api/v1/agent/threads/{thread_id}/messages/stream`
- `useAgentPanelController.ts` now stays on panel composition, while `useAgentPanelQueries.ts` owns query polling/derived read models and `useAgentThreadActions.ts` owns thread lifecycle mutations plus cache reconciliation
- `useAgentComposerRuntime.ts` now stays focused on composer UI state, while `useAgentComposerActions.ts` owns bulk launches, stream sends, and stop-run orchestration

## Usage And Activity

- cumulative usage bar shows `Context`, `Total input`, `Output`, `Cache read`, `Cache hit rate`, and total cost
- `Context` comes from backend persisted run snapshots
- live activity is driven by `run_event`; usage totals remain query-time read models rather than incremental SSE counters
- run summary cards count pending change types across entries, accounts, groups, tags, and entities
