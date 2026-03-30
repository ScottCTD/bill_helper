# Billing Assistant Agent

This feature doc describes the current billing assistant architecture, prompt shape, exact runtime-visible tool contracts, and the `bh` CLI contract the agent uses through the workspace terminal.

## Agent UX Quick Path

1. Open the app and navigate to the Agent route.
2. Create or select a conversation thread.
3. Pick the next-run model from the composer dropdown if needed, attach optional images/PDFs, keep `OCR` on for text-first parsing or leave it off for vision-first sends, let preparation finish or continue in the background, then send.
4. Review the live run timeline:
   - user and assistant messages render inline
   - progress updates and tool-call events appear during execution
   - untitled threads are gated so the first model step can only call `rename_thread`
5. Open the thread review modal after proposals are created.
6. Approve, reject, reopen, or batch-process proposals.
7. Only approved proposals mutate real owner-scoped ledger data.

## Overview

The current assistant is a review-gated tool-calling runtime with a deliberately small model-visible surface:

- the model sees only `rename_thread`, `send_intermediate_update`, `add_user_memory`, `terminal`, and `read_image`
- Bill Helper app reads, proposal creation/updates/removal, and review actions now happen through the installed `bh` CLI inside the workspace container
- `terminal` is the bridge for both local workspace file work and backend-backed Bill Helper operations
- `read_image` is the narrow multimodal escape hatch for loading specific `/workspace/...` images only when attachment hints or later workspace work make visual inspection necessary
- proposals still create `AgentChangeItem` rows first; direct ledger mutation still happens only in review apply handlers

The old read/proposal/review modules still exist internally, but no longer as direct model-facing tools. They are now backend building blocks reused by proposal HTTP routes, normalization, patching, and apply logic.

## Core Components

| Component | Files | Responsibility |
| --- | --- | --- |
| Runtime | `backend/services/agent/runtime.py`, `backend/services/agent/runtime_loop.py`, `backend/services/agent/run_orchestrator.py` | Tool-calling loop, event persistence, final assistant completion, and streaming/background adapters |
| Model client | `backend/services/agent/model_client.py`, `backend/services/agent/model_client_support/` | LiteLLM integration, retry behavior, streaming delta normalization, and usage accounting |
| Prompt assembly | `backend/services/agent/system_prompt.j2`, `backend/services/agent/prompts.py` | Behavior rules, current-user context, `bh` cheat sheet insertion, and memory injection |
| Message history | `backend/services/agent/message_history.py`, `backend/services/agent/message_history_content.py`, `backend/services/agent/attachment_content.py` | Thread history shaping, attachment extraction, PDF/image handling, and review/interruption prefixing |
| Runtime-visible tool catalog | `backend/services/agent/tool_runtime_support/catalog.py`, `backend/services/agent/tool_runtime_support/catalog_session.py`, `backend/services/agent/tool_runtime_support/catalog_terminal.py`, `backend/services/agent/tool_runtime_support/catalog_image.py` | Exact tool schemas exposed to the model |
| Workspace execution | `backend/services/agent/terminal.py`, `backend/services/agent/read_image.py`, `backend/services/docker_cli.py`, `backend/services/agent_workspace.py` | Workspace startup, short-lived session injection, shell execution, on-demand image reads, output truncation, and secret scrubbing |
| CLI | `backend/cli/main.py`, `backend/cli/support.py`, `backend/cli/rendering.py`, `backend/cli/reference.py` | Thin HTTP client, compact/text rendering, and prompt/doc reference metadata |
| Internal domain helpers | `backend/services/agent/read_tools/`, `backend/services/agent/proposals/`, `backend/services/agent/proposal_http.py`, `backend/services/agent/proposal_patching.py` | Lookup helpers plus proposal normalization, metadata, and patching reused behind APIs and review/apply |
| Review/apply | `backend/services/agent/reviews/`, `backend/services/agent/apply/`, `backend/routers/agent.py`, `backend/routers/agent_proposals.py` | Proposal inspection, approve/reject/reopen transitions, reviewer overrides, and canonical mutations |
| Frontend agent UI | `frontend/src/features/agent/` | Thread list, composer, run timeline, tool blocks, and review modal |

## Runtime Flow

1. User sends a message to an agent thread.
2. If the user attached files in the composer first, backend has already persisted and parsed those draft uploads under canonical `user_files`.
3. Backend persists the message, binds any uploaded attachments (or inline request files), and creates a new `agent_runs` row.
4. Runtime builds the system prompt, current-user context, entity-category context, user memory section, and message history.
5. If the thread is untitled, the runtime exposes only `rename_thread` and requests that tool explicitly.
6. After the thread has a valid title, the runtime exposes the five-tool catalog.
7. The model uses `send_intermediate_update` before meaningful tool-call batches.
8. For Bill Helper app work, the model calls `terminal` and executes `bh ...` inside the workspace container.
9. `terminal` ensures the workspace is running, mints a short-lived backend session, injects `BH_*` env, executes `bash -lc`, truncates output when needed, and revokes the temporary session afterward.
10. When an upload hint lists related image paths, the model can call `read_image` later to append only the selected `/workspace/...` images for visual inspection.
11. `bh` calls backend routes for reads and current-thread proposal lifecycle actions.
12. Proposal creation stores pending `AgentChangeItem` rows scoped to the current thread and run.
13. Human review approves, rejects, or reopens proposals.
14. Only approval apply handlers mutate the real domain tables.

## Prompt Shape

The system prompt is a markdown document with:

- `## Identity`
- `## Operating Rules`
- `### Tool Use`
- `## bh Reference`
- `## Proposal Workflow`
- proposal workflow rules for duplicate checks, proposal inspection, and proposal revision
- `## Domain Rules`
- domain-specific rules for entries, tags, entities, accounts, snapshots, and groups
- `## Error Recovery`
- `## Final Response`
- `## Current User Context`
- `### Entity Category Reference`
- `### Account Context`
- `### Agent Memory`

Important current behavior:

- prompt guidance explicitly routes Bill Helper app work through `terminal` plus `bh`
- the prompt embeds a concise `bh` cheat sheet, not full tool schema docs
- raw `curl` and ad hoc Python are discouraged when a `bh` command exists
- duplicate checks, entity/tag/account grounding, group workflow rules, and review-continuation rules still live in the prompt

## Runtime-Visible Tool Contracts

The model-visible tool surface is intentionally small, but it is still documented exactly here.

### Attachment Content The Agent Sees

For a newly uploaded PDF or image bundle, the initial user turn is text-first. The agent sees:

- one attachment text block per uploaded file before the user’s free-text prompt
- absolute workspace paths, including:
  - `raw.<ext>`
  - `parsed.md`
  - all related image paths under `/workspace/uploads/...`
- a short note telling the agent to use `read_image` only when visual inspection is needed
- the full `parsed.md` contents inline under a `--- parsed.md ---` delimiter

When the composer keeps OCR enabled, the initial attachment block does not include any eager `image_url` parts.
When the composer disables OCR for a vision-capable model, images are sent as direct `image_url` parts and PDFs are sent as bundle image parts instead of inline `parsed.md` text.
In the app UI, vision-capable models default the composer `OCR` toggle off for newly attached files, while non-vision models force it on.

<!-- GENERATED:runtime-tool-contracts:start -->
### `add_user_memory`

Description:

Append new persistent user-memory items. Use this only when the user clearly asks you to remember/store a standing preference, rule, or hint for future runs. This tool is add-only: do not use it to mutate or remove existing memory.

Arguments:

- `memory_items: list[string]` required
  description: New persistent memory items to append. Each item should be a short standalone user preference, rule, or hint.
  constraints: minItems=1, maxItems=20

### `rename_thread`

Description:

Rename the current thread to a short 1-3 word topic. Use this right after the first user message in a new thread. After that, only rename when the user explicitly asks or the topic shifts substantially.

Arguments:

- `title: string` required
  description: Short thread title/topic in 1-3 words.
  constraints: minLength=1, maxLength=80

### `send_intermediate_update`

Description:

Call this tool before calling other tools (but after rename_thread). Call this tool again only for meaningful transitions between tool calls; do not call it on every tool step.

Arguments:

- `message: string` required
  description: A short, user-visible progress note. Use plain text or inline markdown (e.g. **bold**, `code`, *italic*) for emphasis when helpful.
  constraints: minLength=1, maxLength=400

### `terminal`

Description:

Use this tool for shell work inside the current user's workspace container. Use `bh` for Bill Helper app operations, standard shell commands for local work under /workspace, and read-only inspection under /workspace/uploads. Use `bh` when the task is about the Bill Helper app. 

Arguments:

- `command: string` required
  description: Shell command to execute verbatim via `bash -lc`. May include newlines, pipes, redirects, command substitution, or heredocs.
  constraints: minLength=1
- `cwd: string | null`
  description: Optional working directory inside the workspace container. Defaults to the writable scratch root `/workspace/scratch`.
  constraints: default=None
- `timeout_seconds: integer`
  description: Command timeout in seconds. Defaults to 120. Allowed range: 1 to 600.
  constraints: minimum=1, maximum=600, default=120

### `read_image`

Description:

Load one or more image files that already exist inside the current user's workspace container and append them for visual inspection. Use this when an attachment note lists related image paths or when you discover relevant image files under /workspace.

Arguments:

- `paths: list[string]` required
  description: Absolute image paths inside the current user's workspace container. Use paths already shown in attachment workspace hints or discovered in `/workspace`.
  constraints: minItems=1
<!-- GENERATED:runtime-tool-contracts:end -->

### `read_image` Output Contract

On success, the backend stores the normal tool-call payload and also appends a multimodal `role=tool` message to the next model call.

Persisted tool-call JSON:

```json
{
  "status": "ok",
  "summary": "loaded N image(s)",
  "paths": [
    "/workspace/uploads/2026-03-22/example/raw.png",
    "/workspace/scratch/chart.png"
  ],
  "image_count": 2
}
```

Model-facing tool message content:

```json
[
  {
    "type": "text",
    "text": "Loaded image(s) for visual inspection:\n- /workspace/uploads/2026-03-22/example/raw.png\n- /workspace/scratch/chart.png"
  },
  {
    "type": "image_url",
    "image_url": {
      "url": "data:image/png;base64,..."
    }
  },
  {
    "type": "image_url",
    "image_url": {
      "url": "data:image/png;base64,..."
    }
  }
]
```

Failure behavior:

- non-vision models receive a normal tool error and no image parts are appended
- invalid paths, missing files, non-image files, paths outside `/workspace`, and over-limit requests fail the whole tool call
- duplicate input paths are silently deduped while preserving first-seen order

## `bh` CLI Contract

`bh` is the canonical app-operation interface for both the agent and humans in the workspace IDE terminal.

Current behavior:

- `bh` is a thin HTTP client; it never mutates the database or canonical files directly
- auth and backend reachability come from `BH_*` env or `/workspace/.ide/bh-env.json`
- non-TTY output defaults to `compact`
- TTY output defaults to `text`
- `json` is explicit opt-in only
- compact output never uses ANSI color
- compact list outputs use 8-character ids when unique in the current result set, and fall back to full ids on collisions
- displayed short ids are reusable across follow-up `bh` reads, including proposal inspection commands and nested proposal references inside proposal payloads, because `bh` resolves them to canonical ids before the final API call
- proposal commands use `BH_THREAD_ID` and `BH_RUN_ID` from the active agent run

Interactive IDE launch refreshes:

- `/workspace/.ide/bh-env.json`
- `/workspace/.ide/bh-shell-env.sh`

That lets humans run `bh ...` directly in the IDE terminal without manual exports.

### Compact Output Contract

Compact output is line-oriented and token-efficient:

- first line is usually `OK`
- summary metadata uses `summary: ...`
- list outputs emit one `schema: ...` line that defines fixed column order
- each following row is a `|`-delimited record
- `\`, `|`, and newlines are escaped inside cell values
- repetitive field names are omitted from rows

### Canonical `bh` Cheat Sheet

<!-- GENERATED:bh-cheat-sheet:start -->
Use `bh` for Bill Helper app reads and current-thread proposal creation and proposal mutation.

- Agent calls should expect `compact` output by default; use `--format text` or `--format json` only when needed.
- Every command also accepts `--format {compact,json,text}` as an optional global override.
- List output uses 8-character ids when unique in the current result set; collisions fall back to full ids.
- Compact output is line-oriented: one `schema:` line defines column order, then one escaped `|`-delimited row per record.
- Read commands work in the human IDE terminal. Any `create`, `update`, `remove`, `add-member`, `remove-member`, or `proposals` command requires the current agent-run env (`BH_THREAD_ID` and `BH_RUN_ID`).
- Inspect before mutating: read entries/tags/accounts/entities/groups/proposals first, then create resource-scoped proposals.
- `bh proposals update` and `bh proposals remove` only work for pending proposals in the current thread.

Command specifications:

### `bh status`
- Purpose: Show current auth, workspace, thread, and run context.
- Required arguments: none.
- Optional arguments: none.

### `bh entries list`
- Purpose: List entries.
- Required arguments: none.
- Optional arguments:
  - `--start-date YYYY-MM-DD: inclusive lower bound on entry date.`
  - `--end-date YYYY-MM-DD: inclusive upper bound on entry date.`
  - `--kind KIND: entry kind filter, for example EXPENSE, INCOME, or TRANSFER.`
  - `--currency CODE: 3-letter currency code filter.`
  - `--account-id ID: account id or unique short id prefix filter.`
  - `--source TEXT: free-text source filter.`
  - `--tag NAME: tag-name filter.`
  - `--filter-group-id ID: group id or unique short id prefix filter.`
  - `--limit N: integer result limit. Default 20.`
  - `--offset N: integer result offset. Default 0.`

### `bh entries get <entry_id>`
- Purpose: Get one entry.
- Required arguments:
  - `<entry_id>: full entry id or unique short id prefix.`
- Optional arguments: none.

### `bh entries create`
- Purpose: Create an entry proposal in the current thread.
- Required arguments:
  - `--kind {EXPENSE,INCOME,TRANSFER}: entry kind.`
  - `--date YYYY-MM-DD: entry date.`
  - `--name TEXT: human-readable entry name.`
  - `--amount-minor INT: integer minor units, for example 1234 for 12.34.`
  - `--from-entity TEXT: source entity name.`
  - `--to-entity TEXT: destination entity name.`
- Optional arguments:
  - `--currency-code CODE: optional 3-letter currency code. Defaults to runtime settings when omitted.`
  - `--tag NAME: tag name. Repeat for multiple tags.`
  - `--markdown-notes TEXT: optional markdown notes.`

### `bh entries update <entry_id>`
- Purpose: Create an entry-update proposal in the current thread.
- Required arguments:
  - `<entry_id>: full entry id or unique short id prefix.`
  - `exactly one of `--patch-json JSON` or `--patch-file PATH`.`
- Optional arguments: none.
- Notes:
  - JSON/PATH must contain a patch object.

### `bh entries remove <entry_id>`
- Purpose: Create an entry-delete proposal in the current thread.
- Required arguments:
  - `<entry_id>: full entry id or unique short id prefix.`
- Optional arguments: none.

### `bh accounts list`
- Purpose: List accounts.
- Required arguments: none.
- Optional arguments: none.

### `bh accounts create`
- Purpose: Create an account proposal in the current thread.
- Required arguments:
  - `--name TEXT: account display name.`
  - `--currency-code CODE: 3-letter currency code such as CAD or USD.`
- Optional arguments:
  - `--markdown-body TEXT: optional markdown description.`
  - `--is-active: mark the account as active.`
  - `--inactive: mark the account as inactive.`
- Notes:
  - If neither `--is-active` nor `--inactive` is provided, the proposal defaults to active.

### `bh accounts update <account_ref>`
- Purpose: Create an account-update proposal in the current thread.
- Required arguments:
  - `<account_ref>: exact account name, full id, or unique short id prefix.`
  - `exactly one of `--patch-json JSON` or `--patch-file PATH`.`
- Optional arguments: none.
- Notes:
  - JSON/PATH must contain a patch object.

### `bh accounts remove <account_ref>`
- Purpose: Create an account-delete proposal in the current thread.
- Required arguments:
  - `<account_ref>: exact account name, full id, or unique short id prefix.`
- Optional arguments: none.

### `bh snapshots list <account_id>`
- Purpose: List account snapshots.
- Required arguments:
  - `<account_id>: full account id or unique short id prefix.`
- Optional arguments: none.

### `bh snapshots reconciliation <account_id>`
- Purpose: Get account reconciliation.
- Required arguments:
  - `<account_id>: full account id or unique short id prefix.`
- Optional arguments:
  - `--as-of YYYY-MM-DD: reconciliation cutoff date.`

### `bh snapshots create`
- Purpose: Create a snapshot proposal in the current thread.
- Required arguments:
  - `--account-id ID: full account id or unique short id prefix.`
  - `--snapshot-at YYYY-MM-DD: snapshot date.`
  - `--balance DECIMAL: decimal balance amount such as 1234.56.`
- Optional arguments:
  - `--note TEXT: optional snapshot note.`

### `bh snapshots remove <account_id> <snapshot_id>`
- Purpose: Create a snapshot-delete proposal in the current thread.
- Required arguments:
  - `<account_id>: full account id or unique short id prefix.`
  - `<snapshot_id>: full snapshot id or unique short id prefix within the account.`
- Optional arguments: none.

### `bh groups list`
- Purpose: List groups.
- Required arguments: none.
- Optional arguments: none.

### `bh groups get <group_id>`
- Purpose: Get one group graph.
- Required arguments:
  - `<group_id>: full group id or unique short id prefix.`
- Optional arguments: none.

### `bh groups create`
- Purpose: Create a group proposal in the current thread.
- Required arguments:
  - `--name TEXT: group display name.`
  - `--group-type {BUNDLE,SPLIT,RECURRING}: group type.`
- Optional arguments: none.

### `bh groups update <group_id>`
- Purpose: Create a group-update proposal in the current thread.
- Required arguments:
  - `<group_id>: full group id or unique short id prefix.`
  - `exactly one of `--patch-json JSON` or `--patch-file PATH`.`
- Optional arguments: none.
- Notes:
  - JSON/PATH must contain a patch object.
  - Patch object format: `{"name":"New Group Name"}`.

### `bh groups remove <group_id>`
- Purpose: Create a group-delete proposal in the current thread.
- Required arguments:
  - `<group_id>: full group id or unique short id prefix.`
- Optional arguments: none.

### `bh groups add-member`
- Purpose: Create a group-membership add proposal.
- Required arguments:
  - `exactly one of `--payload-json JSON` or `--payload-file PATH`.`
- Optional arguments: none.
- Notes:
  - Payload is nested; discriminated by `target.target_type` (`entry` vs `child_group`).
  - Top-level JSON: `{"action":"add","group_ref":{...},"target":{...},"member_role":"PARENT|CHILD"}`. `member_role` is optional unless SPLIT rules require it.
  - Parent `group_ref`: exactly one of `{"group_id":"<id>"}` or `{"create_group_proposal_id":"<id>"}`.
  - Entry target: `{"target_type":"entry","entry_ref":{"entry_id":"<id>"}}` or `entry_ref` with `create_entry_proposal_id`.
  - Child-group target: `{"target_type":"child_group","group_ref":{...}}` with `group_id` or `create_group_proposal_id`.

### `bh groups remove-member`
- Purpose: Create a group-membership removal proposal.
- Required arguments:
  - `exactly one of `--payload-json JSON` or `--payload-file PATH`.`
- Optional arguments: none.
- Notes:
  - Remove supports **existing ids only**; proposal-id references are rejected for parent group and targets.
  - Top-level JSON: `{"action":"remove","group_ref":{"group_id":"<id>"},"target":{...}}` with discriminated `target` (`entry` vs `child_group`).

### `bh entities list`
- Purpose: List entities.
- Required arguments: none.
- Optional arguments: none.

### `bh entities create`
- Purpose: Create an entity proposal in the current thread.
- Required arguments:
  - `--name TEXT: entity display name.`
- Optional arguments:
  - `--category TEXT: optional entity category.`

### `bh entities update <entity_name>`
- Purpose: Create an entity-update proposal in the current thread.
- Required arguments:
  - `<entity_name>: exact entity name.`
  - `exactly one of `--patch-json JSON` or `--patch-file PATH`.`
- Optional arguments: none.
- Notes:
  - JSON/PATH must contain a patch object.

### `bh entities remove <entity_name>`
- Purpose: Create an entity-delete proposal in the current thread.
- Required arguments:
  - `<entity_name>: exact entity name.`
- Optional arguments: none.

### `bh tags list`
- Purpose: List tags.
- Required arguments: none.
- Optional arguments: none.

### `bh tags create`
- Purpose: Create a tag proposal in the current thread.
- Required arguments:
  - `--name TEXT: tag name.`
- Optional arguments:
  - `--type TEXT: optional tag type/category.`

### `bh tags update <tag_name>`
- Purpose: Create a tag-update proposal in the current thread.
- Required arguments:
  - `<tag_name>: exact tag name.`
  - `exactly one of `--patch-json JSON` or `--patch-file PATH`.`
- Optional arguments: none.
- Notes:
  - JSON/PATH must contain a patch object.

### `bh tags remove <tag_name>`
- Purpose: Create a tag-delete proposal in the current thread.
- Required arguments:
  - `<tag_name>: exact tag name.`
- Optional arguments: none.

### `bh proposals list`
- Purpose: List proposals in the current thread.
- Required arguments: none.
- Optional arguments:
  - `--proposal-type TYPE: proposal type filter.`
  - `--proposal-status STATUS: proposal status filter.`
  - `--change-action ACTION: change-action filter.`
  - `--proposal-id ID: full proposal id or unique short id prefix filter.`
  - `--limit N: integer result limit. Default 20.`

### `bh proposals get <proposal_id>`
- Purpose: Get one proposal by full id or unique prefix.
- Required arguments:
  - `<proposal_id>: full proposal id or unique short id prefix.`
- Optional arguments: none.

### `bh proposals update <proposal_id>`
- Purpose: Update one pending proposal by id.
- Required arguments:
  - `<proposal_id>: full proposal id or unique short id prefix.`
  - `exactly one of `--patch-json JSON` or `--patch-file PATH`.`
- Optional arguments: none.
- Notes:
  - JSON/PATH must contain a patch object.

### `bh proposals remove <proposal_id>`
- Purpose: Remove one pending proposal by id.
- Required arguments:
  - `<proposal_id>: full proposal id or unique short id prefix.`
- Optional arguments: none.

Compact list schemas:
- `entries_list` -> `id|date|kind|amount_minor|currency|name|from|to|tags`
- `accounts_list` -> `id|name|currency|active`
- `snapshots_list` -> `id|date|balance_minor|note`
- `groups_list` -> `id|type|name|descendants|first_date|last_date`
- `entities_list` -> `name|category`
- `tags_list` -> `name|type|description`
- `proposals_list` -> `id|status|change_type|summary`

Common flows:
- Inspect recent matching entries: `bh entries list --source "farm boy" --limit 10`
- Inspect current proposal state: `bh proposals list --proposal-status PENDING_REVIEW --limit 20`
- Create a tag proposal: `bh tags create --name grocery --type expense`
- Create an entry-update proposal: `bh entries update 8bf2fa83 --patch-json '{"tags":["grocery","one_time"]}'`
- Create an account proposal: `bh accounts create --name "Wealthsimple Cash" --currency-code CAD --inactive`
- Create a snapshot proposal: `bh snapshots create --account-id 1a2b3c4d --snapshot-at 2026-03-15 --balance 1234.56 --note "statement balance"`
- Update a pending proposal: `bh proposals update a1b2c3d4 --patch-json '{"patch.tags":["grocery"]}'`
- Remove a pending proposal: `bh proposals remove a1b2c3d4`
- Create a group-membership add proposal: `bh groups add-member --payload-json '{"action":"add","group_ref":{"group_id":"a971c92e"},"target":{"target_type":"entry","entry_ref":{"entry_id":"8bf2fa83"}}}'`

<!-- GENERATED:bh-cheat-sheet:end -->

## Proposal And Review Lifecycle

Proposal lifecycle is now thread-scoped through the CLI and review APIs:

1. the agent runs a resource-scoped `bh ... create|update|remove|add-member|remove-member ...` command
2. backend stores a pending `AgentChangeItem`
3. `bh proposals list` and `bh proposals get` inspect thread-local proposal history
4. `bh proposals update` and `bh proposals remove` can change or drop pending proposals before review
5. the human review UI drives approve, reject, and reopen
6. approval applies the change through the existing backend apply handlers

## API Surface Behind The CLI

Thread-scoped proposal routes:

- `GET /api/v1/agent/threads/{thread_id}/proposals`
- `GET /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`
- `POST /api/v1/agent/threads/{thread_id}/proposals`
- `PATCH /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`
- `DELETE /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`

Review routes:

- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`
- `POST /api/v1/agent/change-items/{item_id}/reopen`

Read routes used by `bh` include:

- `GET /api/v1/auth/me`
- `GET /api/v1/workspace`
- `GET /api/v1/entries`
- `GET /api/v1/entries/{entry_id}`
- `GET /api/v1/accounts`
- `GET /api/v1/accounts/{account_id}/snapshots`
- `GET /api/v1/accounts/{account_id}/reconciliation`
- `GET /api/v1/groups`
- `GET /api/v1/groups/{group_id}`
- `GET /api/v1/entities`
- `GET /api/v1/tags`

## Workspace And Configuration Notes

- `BILL_HELPER_WORKSPACE_BACKEND_BASE_URL` controls container-to-backend reachability
- terminal execution injects `BH_API_BASE_URL`, `BH_AUTH_TOKEN`, `BH_THREAD_ID`, `BH_RUN_ID`, `BH_WORKSPACE_ROOT`, and `BH_DATA_ROOT`
- the auth token is a short-lived session created for the thread owner and revoked after the command finishes
- the configured workspace image must include the Bill Helper package, the `bh` entrypoint, and normal shell/file utilities
- `terminal` scrubs the temporary auth token from captured stdout/stderr

## Verification Expectations

When this surface changes, useful checks include:

- CLI unit tests for format defaults and compact renderer behavior
- workspace terminal execution against a disposable backend
- proposal create/list/get through `bh`
- review approve/reject/reopen through `bh`
- browser review/apply flow on an isolated backend
- docs and prompt sync checks

## Related Files

- [backend/cli/main.py](../../backend/cli/main.py)
- [backend/cli/support.py](../../backend/cli/support.py)
- [backend/cli/rendering.py](../../backend/cli/rendering.py)
- [backend/cli/reference.py](../../backend/cli/reference.py)
- [backend/services/agent/tool_runtime_support/catalog.py](../../backend/services/agent/tool_runtime_support/catalog.py)
- [backend/services/agent/tool_runtime_support/catalog_terminal.py](../../backend/services/agent/tool_runtime_support/catalog_terminal.py)
- [backend/services/agent/system_prompt.j2](../../backend/services/agent/system_prompt.j2)
- [backend/services/agent/prompts.py](../../backend/services/agent/prompts.py)
- [backend/services/agent/terminal.py](../../backend/services/agent/terminal.py)
- [backend/services/workspace_cli_env.py](../../backend/services/workspace_cli_env.py)
- [backend/routers/agent_proposals.py](../../backend/routers/agent_proposals.py)
