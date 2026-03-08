# API Agent

## Threads

### `GET /agent/threads`

List threads in most-recently-updated order. Response: `AgentThreadSummaryRead[]`

Authorization: admin principal only.

Each row includes:

- thread metadata
- `last_message_preview`
- `pending_change_count`
- `has_running_run`

### `POST /agent/threads`

Create a thread. Body: optional `title`. Response: `AgentThreadRead`

Authorization: admin principal only.

If no title is supplied, the thread remains untitled until a later explicit rename.

### `PATCH /agent/threads/{thread_id}`

Rename one thread. Body: `{ "title": string }`. Response: `AgentThreadRead`

Authorization: admin principal only.

Validation:

- title is normalized for internal whitespace
- title must contain 1-5 words
- title must be 80 characters or fewer

### `DELETE /agent/threads/{thread_id}`

Delete one thread and its persisted timeline artifacts. Response: `204`

Authorization: admin principal only.

Behavior:

- cascades deletes for messages, runs, tool calls, change items, and review actions
- removes local upload directories under `{data_dir}/agent_uploads/<message_id>/...`
- rejects delete when any run in the thread is still running

Errors:

- `404` thread not found
- `409` active running run exists

### `GET /agent/threads/{thread_id}`

Fetch timeline-ready thread detail. Response: `AgentThreadDetailRead`

Authorization: admin principal only.

Includes:

- `thread`
- `messages`
- `runs`
- per-run `change_items` used by the frontend to build the thread-scoped review surface
- legacy persisted change rows with unsupported `change_type` values are skipped from `change_items` so thread history keeps loading on current clients
- `configured_model_name`
- `current_context_tokens`
- each run carries its own `model_name`; clients should treat the newest run model as the active conversation model when present
- compact tool-call snapshots by default
- ordered run `events[]`
- nullable usage counters and derived pricing fields (`input_cost_usd`, `output_cost_usd`, `total_cost_usd`)

## Message Send

### `POST /agent/threads/{thread_id}/messages`

Create a user message and run the agent in background.

Authorization: admin principal only.

Content type: `multipart/form-data`

Form fields:

- `content` (optional if files are present)
- `model_name` (optional explicit model selection; must match one of the `available_agent_models` returned by `GET /settings`)
- `files` (0..N image or PDF attachments)

Behavior:

- validates attachment count and size limits
- persists message and attachments
- creates an `agent_runs` row with initial `status=running`
- starts bounded tool-calling execution in background
- PDFs are parsed with PyMuPDF first; vision-capable models also receive rendered page images
- provider routing resolves through LiteLLM using the requested `model_name` when supplied, otherwise the configured default model
- proposal tool outputs include `proposal_id` and `proposal_short_id`
- pending proposals can later be edited or removed while still pending

Response: `AgentRunRead`

Errors:

- `400` invalid payload
- `400` selected `model_name` is not enabled in runtime settings
- `404` thread not found
- `503` provider credentials unavailable

### `POST /agent/threads/{thread_id}/messages/stream`

Create a user message and run the agent with SSE.

Authorization: admin principal only.

Content type: `multipart/form-data`

Behavior:

- uses the same validation and persistence rules as the non-stream endpoint
- executes in-request and streams incremental events
- if the client disconnects, the run continues in background
- response payload shape stays aligned with the non-stream endpoint: run snapshots expose the effective per-run `model_name`

Response content type: `text/event-stream`

Event contract:

- `reasoning_delta`
- `text_delta`
- `run_event`
  - shape: `{ type, run_id, event, tool_call? }`
  - `tool_call` is present only for tool lifecycle events and uses the compact `AgentToolCallRead` shape (`has_full_payload=false`, payload fields omitted)
  - `rename_thread` starts streaming as a compact tool-call event before the final assistant message; clients can hydrate the tool row immediately through `GET /agent/tool-calls/{tool_call_id}` and update thread labels without waiting for run completion

Usage notes:

- usage totals are persisted on the run record and read from snapshot endpoints
- when cache metadata is present, prompt-side pricing uses LiteLLM's cache-aware rates but remains exposed through the existing `input_cost_usd` and `total_cost_usd` fields
- retries after partial streamed text suppress already-emitted prefixes
- `reasoning_delta` is transient live stream output; the durable record remains the later persisted `run_event` with `event_type=reasoning_update`
- expand a streamed compact tool row through `GET /agent/tool-calls/{tool_call_id}` when full arguments or results are needed

## Runs And Tool Calls

### `GET /agent/runs/{run_id}`

Get a run snapshot. Response: `AgentRunRead`

Authorization: admin principal only.

Returned payload includes:

- lifecycle metadata
- full tool calls (`has_full_payload=true`)
- change items (legacy unsupported persisted change rows are omitted)
- usage counters
- derived pricing fields, where `input_cost_usd` is the full prompt-side cost after cache-aware pricing, `output_cost_usd` remains the completion-side cost, and `total_cost_usd` is their sum

### `GET /agent/tool-calls/{tool_call_id}`

Get one fully hydrated tool-call payload. Response: `AgentToolCallRead`

Authorization: admin principal only.

Errors:

- `404` tool call not found

### `POST /agent/runs/{run_id}/interrupt`

Interrupt a currently running run. Response: `AgentRunRead`

Authorization: admin principal only.

Behavior:

- running runs are marked `failed` with `error_text = "Run interrupted by user."`
- already terminal runs are returned unchanged

Errors:

- `404` run not found

## Review Actions

### `POST /agent/change-items/{item_id}/approve`

Approve and apply one proposal item. Response: `AgentChangeItemRead`

Authorization: admin principal only.

Body:

- `note` (optional)
- `payload_override` (optional; supported for `create_entry`, `update_entry`, `create_group`, `update_group`, `create_group_member`, `create_tag`, `update_tag`, `create_entity`, and `update_entity`)

State rules:

- allowed for any non-`APPLIED` item
- returns `409` if already applied
- transitions to `APPLY_FAILED` on apply failure

Apply behavior covers:

- entry create, update, and soft-delete
- group create, rename, delete, and direct-member add/remove
- tag create, update, and delete
- entity create, update, and delete

Notes:

- the endpoint shape is unchanged; reviewer edits are sent through `payload_override`
- invalid `payload_override` payloads return `422` and leave the item unchanged
- group-member proposals that reference pending `create_group` or `create_entry` proposals return `422` until those dependencies are approved and applied
- when reviewer edits are present, later agent turns receive a compact `review_override=...` summary in the prepended review-results context

### `POST /agent/change-items/{item_id}/reject`

Reject one proposal item. Response: `AgentChangeItemRead`

Authorization: admin principal only.

Body:

- `note` (optional)
- `payload_override` (optional; supported for the same editable change types as approve)

State rules:

- allowed for any non-`APPLIED` item
- returns `409` if already applied

Behavior:

- stores reviewer edits back onto the proposal payload before marking it `REJECTED`
- does not apply domain changes

### `POST /agent/change-items/{item_id}/reopen`

Move one non-applied proposal item back to pending review. Response: `AgentChangeItemRead`

Authorization: admin principal only.

Body:

- `note` (optional)
- `payload_override` (optional; supported for the same editable change types as approve)

State rules:

- allowed for any non-`APPLIED` item
- returns `409` if already applied

Behavior:

- stores reviewer edits back onto the proposal payload
- sets status back to `PENDING_REVIEW`
- does not apply domain changes

## Attachments

### `GET /agent/attachments/{attachment_id}`

Serve one uploaded agent attachment.

Authorization: admin principal only.

Response: binary file with stored MIME type.
