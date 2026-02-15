# Completed Proposal: Agent Workspace Redesign (Conversation UX + Run Observability)

## Draft Date

- 2026-02-09

## Why This Proposal Exists

The current Agent workspace is functional, but the conversation experience does not yet match a modern, minimal chat UX and does not expose enough runtime observability for confident review.

This proposal defines a focused redesign that keeps the current overall page layout and thread model, while improving message rendering, attachment UX, tool-call transparency, and thread-level usage visibility.

## Current Behavior (Baseline)

- Header title is static (`Agent`) and does not surface the active model in the title.
- Message cards include a nested text container (`pre` inside bubble), creating a double-box chat appearance.
- Assistant content is shown as plain preformatted text rather than rendered markdown.
- Composer attachments are selected via file input and shown as filename text only, with no inline thumbnail/icon list, click-to-preview, or per-file removal control.
- Tool-call data exists, but presentation is basic and not optimized for progressive observability during run execution.
- Run/tool-call blocks are currently mapped under user messages (`user_message_id`), which places them in the user-side column instead of assistant-side conversational flow.
- No compact thread-level usage footer is shown for input/output/cache token accounting.

## Goals

1. Show the active model in the Agent title (`Agent (<model>)`).
2. Deliver a cleaner, modern, minimal message surface by removing redundant nested message boxes.
3. Render assistant output as markdown.
4. Improve image attachment UX in the composer with compact, removable preview chips.
5. Make tool calls observable in near real time with collapsible details.
6. Place tool/run events in the assistant-side timeline column.
7. Add a compact thread usage footnote for token/cache metrics.

## Non-Goals (V1)

1. No change to core thread CRUD flow or thread-list navigation model.
2. No model-switching control in this iteration (display-only model context).
3. No migration from polling to websocket/SSE required for v1 (polling-based near real time is acceptable).

## Proposed UX Direction

## 1) Header Title With Model Context

- Replace static title with `Agent (<model>)`.
- Resolve `<model>` from the most recent run in the selected thread.
- Fallback when unavailable: `Agent (unknown model)` or current configured default.

## 2) Modern Minimal Message Surface

- Keep one primary bubble container per message.
- Remove inner boxed text area so message text is rendered directly in the bubble body.
- Preserve existing role alignment pattern:
  - assistant on left
  - user on right
- Keep timestamp and role label subtle (small muted text).

## 3) Assistant Markdown Rendering

- Render `content_markdown` as markdown for assistant messages instead of raw `<pre>`.
- Support common blocks: headings, lists, code fences, links, and paragraphs.
- Use safe markdown rendering/sanitization defaults.
- User messages can remain plain text render in v1 if desired for simplicity.

## 4) Composer Image Attachment Chips

- Show selected images in a compact row above the compose textarea.
- Each attachment item should include:
  - small thumbnail/icon
  - filename (truncated)
  - remove (`x`) control
- Clicking a chip opens a preview surface (lightbox/modal/popover).
- Removing a chip updates pending send payload immediately.

## 5) Tool-Call Observability (Collapsible + Near Real Time)

- Render tool calls as timeline sub-events with progressive visibility while run status is `running`.
- Each tool call is a collapsible panel, default collapsed, with summary row:
  - tool name
  - status
  - timestamp
- Expanded state shows:
  - arguments/input (`input_json`)
  - return payload/error (`output_json`)
- Keep ordering deterministic by call creation order.
- For large payloads, keep collapsed-by-default with scrollable/truncated detail blocks.

## 6) Place Run/Tool Blocks In Assistant Column

- Anchor run/tool rendering primarily by `assistant_message_id`.
- While a run is active and assistant message is not yet available, show a temporary assistant-side "working" block.
- Once assistant message exists, associate the run/tool blocks with that assistant event to avoid user-column placement.

## 7) Thread Usage Footnote

- Add a compact metadata row near the timeline footer/composer, for current thread totals:
  - `Input`
  - `Output`
  - `Cache read`
  - `Cache write`
- Small muted font; always visible when a thread is selected.
- Show placeholder (`-`) where metrics are unavailable.

## Data/API Impact

Frontend type additions (planned):

- Extend `AgentRun` with optional usage fields:
  - `input_tokens`
  - `output_tokens`
  - `cache_read_tokens`
  - `cache_write_tokens`

Backend additions (planned, nullable for backward compatibility):

- Persist usage fields on `agent_runs`.
- Populate usage from model response metadata when available.
- Return usage fields in run/thread read APIs.

## Affected Files / Modules (Planned)

Frontend:

- `/path/to/bill_helper/frontend/src/components/agent/AgentPanel.tsx`
- `/path/to/bill_helper/frontend/src/styles.css`
- `/path/to/bill_helper/frontend/src/lib/types.ts`
- `/path/to/bill_helper/frontend/src/lib/api.ts` (if response parsing/type guards need updates)
- optional markdown rendering helper under `/path/to/bill_helper/frontend/src/components/ui/` or existing markdown component reuse

Backend (only for usage footnote support):

- `/path/to/bill_helper/backend/models.py`
- `/path/to/bill_helper/backend/schemas.py`
- `/path/to/bill_helper/backend/services/agent/model_client.py`
- `/path/to/bill_helper/backend/services/agent/runtime.py`
- `/path/to/bill_helper/backend/services/agent/serializers.py`
- migration file under `/path/to/bill_helper/backend/alembic/versions/` if schema columns are introduced

## Operational Impact

- More frequent timeline repaint during active runs to keep tool-call state fresh.
- Larger response payloads if tool I/O and usage metadata are both expanded.
- Attachment preview URLs must be revoked on cleanup to avoid browser memory leaks.

## Constraints / Known Limitations

1. "Real time" in v1 is polling-based and may lag briefly between updates.
2. Historical runs may have missing usage metadata; UI must tolerate nulls.
3. Tool outputs can be large and should be constrained by collapsible/scrollable containers.
4. Markdown rendering must remain sanitized to prevent unsafe HTML/script injection.

## Test Plan

Frontend checks:

1. Header displays `Agent (<model>)` for selected thread context.
2. Message cards no longer show nested inner message boxes.
3. Assistant markdown renders structured content correctly.
4. Selected image attachments appear as removable preview chips before send.
5. Tool-call panels update during active runs and expose arguments/outputs in collapsible details.
6. Run/tool-call blocks render in assistant-side timeline placement.
7. Thread usage footnote appears with correct totals and null-safe placeholders.

Regression checks:

1. Existing send message flow (text + images) remains functional.
2. Existing change-item review actions (approve/reject) remain functional.
3. Thread selection and creation behavior remains unchanged.

## Acceptance Criteria

1. Agent title includes current model context without breaking thread navigation.
2. Chat UI presents one clean bubble surface per message with assistant markdown rendering.
3. Composer supports previewable/removable image chips pre-send.
4. Tool calls are observable, collapsible, and include both input and output payloads.
5. Run/tool-call events are visually aligned with assistant-side conversation flow.
6. Thread usage footnote exposes input/output/cache metrics with graceful fallbacks.
