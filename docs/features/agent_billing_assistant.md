# Billing Assistant Agent

This feature doc describes the current billing assistant architecture, prompt shape, exact runtime-visible tool contracts, and the `bh` CLI contract the agent uses through the workspace terminal.

## Agent UX Quick Path

1. Open the app and navigate to the Agent route.
2. Create or select a conversation thread.
3. Pick the next-run model from the composer dropdown if needed, then send text and optional attachments.
4. Review the live run timeline:
   - user and assistant messages render inline
   - progress updates and tool-call events appear during execution
   - untitled threads are gated so the first model step can only call `rename_thread`
5. Open the thread review modal after proposals are created.
6. Approve, reject, reopen, or batch-process proposals.
7. Only approved proposals mutate real owner-scoped ledger data.

## Overview

The current assistant is a review-gated tool-calling runtime with a deliberately small model-visible surface:

- the model sees only `rename_thread`, `send_intermediate_update`, `add_user_memory`, and `terminal`
- Bill Helper app reads, proposal creation/updates/removal, and review actions now happen through the installed `bh` CLI inside the workspace container
- `terminal` is the bridge for both local workspace file work and backend-backed Bill Helper operations
- proposals still create `AgentChangeItem` rows first; direct ledger mutation still happens only in review apply handlers

The old read/proposal/review modules still exist internally, but no longer as direct model-facing tools. They are now backend building blocks reused by proposal HTTP routes, normalization, patching, and apply logic.

## Core Components

| Component | Files | Responsibility |
| --- | --- | --- |
| Runtime | `backend/services/agent/runtime.py`, `backend/services/agent/runtime_loop.py`, `backend/services/agent/run_orchestrator.py` | Tool-calling loop, event persistence, final assistant completion, and streaming/background adapters |
| Model client | `backend/services/agent/model_client.py`, `backend/services/agent/model_client_support/` | LiteLLM integration, retry behavior, streaming delta normalization, and usage accounting |
| Prompt assembly | `backend/services/agent/system_prompt.j2`, `backend/services/agent/prompts.py` | Behavior rules, current-user context, `bh` cheat sheet insertion, and memory injection |
| Message history | `backend/services/agent/message_history.py`, `backend/services/agent/message_history_content.py`, `backend/services/agent/attachment_content.py` | Thread history shaping, attachment extraction, PDF/image handling, and review/interruption prefixing |
| Runtime-visible tool catalog | `backend/services/agent/tool_runtime_support/catalog.py`, `backend/services/agent/tool_runtime_support/catalog_session.py`, `backend/services/agent/tool_runtime_support/catalog_terminal.py` | Exact tool schemas exposed to the model |
| Workspace execution | `backend/services/agent/terminal.py`, `backend/services/docker_cli.py`, `backend/services/agent_workspace.py` | Workspace startup, short-lived session injection, shell execution, output truncation, and secret scrubbing |
| CLI | `backend/cli/main.py`, `backend/cli/support.py`, `backend/cli/rendering.py`, `backend/cli/reference.py` | Thin HTTP client, compact/text rendering, and prompt/doc reference metadata |
| Internal domain helpers | `backend/services/agent/read_tools/`, `backend/services/agent/proposals/`, `backend/services/agent/proposal_http.py`, `backend/services/agent/proposal_patching.py` | Lookup helpers plus proposal normalization, metadata, and patching reused behind APIs and review/apply |
| Review/apply | `backend/services/agent/reviews/`, `backend/services/agent/apply/`, `backend/routers/agent.py`, `backend/routers/agent_proposals.py` | Proposal inspection, approve/reject/reopen transitions, reviewer overrides, and canonical mutations |
| Frontend agent UI | `frontend/src/features/agent/` | Thread list, composer, run timeline, tool blocks, and review modal |

## Runtime Flow

1. User sends a message to an agent thread.
2. Backend persists the message, attachments, and a new `agent_runs` row.
3. Runtime builds the system prompt, current-user context, entity-category context, user memory section, and message history.
4. If the thread is untitled, the runtime exposes only `rename_thread`.
5. After the thread has a valid title, the runtime exposes the four-tool catalog.
6. The model uses `send_intermediate_update` before meaningful tool-call batches.
7. For Bill Helper app work, the model calls `terminal` and executes `bh ...` inside the workspace container.
8. `terminal` ensures the workspace is running, mints a short-lived backend session, injects `BH_*` env, executes `bash -lc`, truncates output when needed, and revokes the temporary session afterward.
9. `bh` calls backend routes for reads and current-thread proposal lifecycle actions.
10. Proposal creation stores pending `AgentChangeItem` rows scoped to the current thread and run.
11. Human review approves, rejects, or reopens proposals.
12. Only approval apply handlers mutate the real domain tables.

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

Use this tool for shell work inside the current user's workspace container. Use `bh` for Bill Helper app operations, standard shell commands for local work under /workspace, and read-only inspection under /data. Use `bh` when the task is about the Bill Helper app. 

Arguments:

- `command: string` required
  description: Shell command to execute verbatim via `bash -lc`. May include newlines, pipes, redirects, command substitution, or heredocs.
  constraints: minLength=1
- `cwd: string | null`
  description: Optional working directory inside the workspace container. Defaults to the workspace root `/workspace/workspace`.
  constraints: default=None
- `timeout_seconds: integer`
  description: Command timeout in seconds. Defaults to 120. Allowed range: 1 to 600.
  constraints: minimum=1, maximum=600, default=120
<!-- GENERATED:runtime-tool-contracts:end -->

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
- List output uses 8-character ids when unique in the current result set; collisions fall back to full ids.
- Compact output is line-oriented: one `schema:` line defines column order, then one escaped `|`-delimited row per record.
- Read commands work in the human IDE terminal. Any `create`, `update`, `remove`, `add-member`, `remove-member`, or `proposals` command requires the current agent-run env (`BH_THREAD_ID` and `BH_RUN_ID`).
- Inspect before mutating: read entries/tags/accounts/entities/groups/proposals first, then create resource-scoped proposals.
- `bh proposals update` and `bh proposals remove` only work for pending proposals in the current thread.

Common commands:
- `bh status`
- `bh entries list [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--kind KIND] [--currency CODE] [--account-id ID] [--source TEXT] [--tag NAME] [--filter-group-id ID] [--limit N] [--offset N]`
- `bh entries get <entry_id>`
- `bh entries create (--payload-json JSON | --payload-file PATH)`
- `bh entries update <entry_id> (--patch-json JSON | --patch-file PATH)`
- `bh entries remove <entry_id>`
- `bh accounts list`
- `bh accounts create (--payload-json JSON | --payload-file PATH)`
- `bh accounts update <account_ref> (--patch-json JSON | --patch-file PATH)`
- `bh accounts remove <account_ref>`
- `bh snapshots list <account_id>`
- `bh snapshots reconciliation <account_id> [--as-of YYYY-MM-DD]`
- `bh snapshots create (--payload-json JSON | --payload-file PATH)`
- `bh snapshots remove <account_id> <snapshot_id>`
- `bh groups list`
- `bh groups get <group_id>`
- `bh groups create (--payload-json JSON | --payload-file PATH)`
- `bh groups update <group_id> (--patch-json JSON | --patch-file PATH)`
- `bh groups remove <group_id>`
- `bh groups add-member (--payload-json JSON | --payload-file PATH)`
- `bh groups remove-member (--payload-json JSON | --payload-file PATH)`
- `bh entities list`
- `bh entities create (--payload-json JSON | --payload-file PATH)`
- `bh entities update <entity_name> (--patch-json JSON | --patch-file PATH)`
- `bh entities remove <entity_name>`
- `bh tags list`
- `bh tags create (--payload-json JSON | --payload-file PATH)`
- `bh tags update <tag_name> (--patch-json JSON | --patch-file PATH)`
- `bh tags remove <tag_name>`
- `bh proposals list [--proposal-type TYPE] [--proposal-status STATUS] [--change-action ACTION] [--proposal-id ID] [--limit N]`
- `bh proposals get <proposal_id>`
- `bh proposals update <proposal_id> (--patch-json JSON | --patch-file PATH)`
- `bh proposals remove <proposal_id>`

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
- Create a tag proposal: `bh tags create --payload-json '{"name":"grocery","type":"expense"}'`
- Create an entry-update proposal: `bh entries update 8bf2fa83 --patch-json '{"tags":["grocery","one_time"]}'`
- Create an account proposal: `bh accounts create --payload-json '{"name":"Wealthsimple Cash","currency_code":"CAD","is_active":true}'`
- Create a snapshot proposal: `bh snapshots create --payload-json '{"account_id":"1a2b3c4d","snapshot_at":"2026-03-15","balance":"1234.56","note":"statement balance"}'`
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
