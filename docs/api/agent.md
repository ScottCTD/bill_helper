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
- `configured_model_name`
- `current_context_tokens`
- compact tool-call snapshots by default
- ordered run `events[]`
- nullable usage and pricing fields

## Message Send

### `POST /agent/threads/{thread_id}/messages`

Create a user message and run the agent in background.

Authorization: admin principal only.

Content type: `multipart/form-data`

Form fields:

- `content` (optional if files are present)
- `files` (0..N image or PDF attachments)

Behavior:

- validates attachment count and size limits
- persists message and attachments
- creates an `agent_runs` row with initial `status=running`
- starts bounded tool-calling execution in background
- PDFs are parsed with PyMuPDF first; vision-capable models also receive rendered page images
- provider routing resolves through LiteLLM using configured model plus provider credentials
- proposal tool outputs include `proposal_id` and `proposal_short_id`
- pending proposals can later be edited or removed while still pending

Response: `AgentRunRead`

Errors:

- `400` invalid payload
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

Response content type: `text/event-stream`

Event contract:

- `reasoning_delta`
- `text_delta`
- `run_event`
  - shape: `{ type, run_id, event, tool_call? }`
  - `tool_call` is present only for tool lifecycle events and uses the compact `AgentToolCallRead` shape (`has_full_payload=false`, payload fields omitted)

Usage notes:

- usage totals are persisted on the run record and read from snapshot endpoints
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
- change items
- usage counters
- derived pricing fields

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
- `payload_override` (optional; supported for `create_entry`, `update_entry`, `create_tag`, `update_tag`, `create_entity`, and `update_entity`)

State rules:

- allowed only for `PENDING_REVIEW`
- returns `409` if already applied or rejected
- transitions to `APPLY_FAILED` on apply failure

Apply behavior covers:

- entry create, update, and soft-delete
- tag create, update, and delete
- entity create, update, and delete

Notes:

- the endpoint shape is unchanged; reviewer edits are sent through `payload_override`
- when reviewer edits are present, later agent turns receive a compact `review_override=...` summary in the prepended review-results context

### `POST /agent/change-items/{item_id}/reject`

Reject one proposal item. Response: `AgentChangeItemRead`

Authorization: admin principal only.

Body:

- `note` (optional)

State rules:

- allowed only for `PENDING_REVIEW`
- returns `409` if already applied or rejected

## Attachments

### `GET /agent/attachments/{attachment_id}`

Serve one uploaded agent attachment.

Authorization: admin principal only.

Response: binary file with stored MIME type.
