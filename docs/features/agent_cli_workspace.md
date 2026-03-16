# Agent CLI Workspace

This feature doc describes the current agent execution model built around the workspace terminal and the `bh` CLI.

## Why This Exists

The old model-visible tool catalog kept growing across reads, proposals, and review actions. That had two problems:

- it consumed model context with many overlapping tool descriptions
- it made extension work expensive because every new domain capability wanted a new model-facing tool

The current design reduces the model-visible surface to one general workspace terminal tool plus a few tiny session tools, then moves Bill Helper app operations behind the installed `bh` CLI.

## Current Model-Visible Tool Surface

The runtime catalog exposed to the model now contains only:

- `terminal`
- `send_intermediate_update`
- `rename_thread`
- `add_user_memory`

This means the old direct CRUD/read tool surface is fully replaced at the model boundary.

The old read/proposal/review handler modules still exist in backend code, but they are now internal building blocks behind backend APIs and `bh`.

## Terminal Contract

`terminal` executes the provided command verbatim via `bash -lc` inside the current user's Docker workspace container.

Default behavior:

- cwd defaults to `/workspace/workspace`
- multiline shell snippets, heredocs, pipes, redirects, and standard shell composition are supported
- output is truncated safely when needed
- stdout and stderr are returned separately
- duration and exit code are reported
- injected auth secrets are scrubbed from tool output

Injected env per invocation:

- `BH_API_BASE_URL`
- `BH_AUTH_TOKEN`
- `BH_THREAD_ID`
- `BH_RUN_ID`
- `BH_WORKSPACE_ROOT`
- `BH_DATA_ROOT`

The auth token is a short-lived backend session created for the thread owner and revoked after the command finishes.

For human IDE terminal use, workspace IDE launch also refreshes `/workspace/.ide/bh-env.json` plus a sourced shell snippet so `bh` works without manual env exports.

## What `bh` Does

`bh` is a thin HTTP client installed in the workspace image.

It does not mutate the DB directly. All authoritative state changes still go through backend routes and review/apply workflows.

Current command groups:

- `status`
- `entries list|get|create|update|remove`
- `accounts list|snapshots|reconciliation|create|update|remove`
- `groups list|get|create|update|remove|add-member|remove-member`
- `entities list|create|update|remove`
- `tags list|create|update|remove`
- `proposals list|get`

## Proposal And Review Flow

Proposal lifecycle is now thread-scoped in the CLI:

1. the agent runs a resource-scoped `bh ... create|update|remove|add-member|remove-member ...` command
2. backend stores a pending `AgentChangeItem`
3. the review UI approves, rejects, or reopens it
4. approval applies the change through existing backend apply handlers

Thread-scoped proposal commands depend on:

- `BH_THREAD_ID`
- `BH_RUN_ID`

That lets every proposal stay attached to a concrete thread/run review history, and it also keeps proposal commands unavailable in ordinary human IDE terminals.

## API Surface Behind The CLI

Key proposal routes:

- `GET /api/v1/agent/threads/{thread_id}/proposals`
- `GET /api/v1/agent/threads/{thread_id}/proposals/{proposal_id}`
- `POST /api/v1/agent/threads/{thread_id}/proposals`

Review routes remain frontend-driven human review endpoints:

- `POST /api/v1/agent/change-items/{item_id}/approve`
- `POST /api/v1/agent/change-items/{item_id}/reject`
- `POST /api/v1/agent/change-items/{item_id}/reopen`

## Workspace Image Requirements

The configured workspace image must include:

- the Bill Helper Python package
- the `bh` console entry point
- the normal shell/file utilities the agent relies on

The current image is built from:

- [docker/agent-workspace.dockerfile](/Users/scottcui/.codex/worktrees/479c/bill_helper/docker/agent-workspace.dockerfile)

It installs the package from the repository source tree so the CLI is available at runtime.

## What Replaced The Legacy CRUD Tools

At the runtime boundary, yes: the old direct CRUD tools are replaced.

That means:

- the model no longer receives `list_*`, `propose_*`, `update_pending_proposal`, or `remove_pending_proposal` as direct tools
- the model should use `terminal` plus `bh`

What is still retained internally:

- proposal validation and normalization logic
- read helper implementations
- review/apply workflows
- metadata and patching helpers

Those internals remain valuable because the CLI and proposal HTTP routes reuse them.

## Operational Notes

- `BILL_HELPER_WORKSPACE_BACKEND_BASE_URL` controls container-to-backend reachability and defaults to `http://host.docker.internal:8000/api/v1`
- local e2e runs that start the backend on a different port must override that env
- direct `curl` or ad hoc Python from the workspace is still possible, but the prompt and docs now prefer `bh` whenever a command exists
- human IDE terminals read API/auth defaults from `/workspace/.ide/bh-env.json` when explicit env vars are absent

## Verification Expectations

When this surface changes, useful checks include:

- CLI command execution inside the workspace container
- proposal create/list/get through `bh`
- browser review/apply flow on a disposable backend
- workspace container startup with the current image

## Related Files

- [backend/cli/support.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/cli/support.py)
- [backend/cli/main.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/cli/main.py)
- [backend/services/agent/workspace_command.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/workspace_command.py)
- [backend/services/agent/tool_runtime_support/catalog.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/tool_runtime_support/catalog.py)
- [backend/services/agent/tool_runtime_support/catalog_workspace.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/tool_runtime_support/catalog_workspace.py)
- [backend/routers/agent_proposals.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/routers/agent_proposals.py)
- [backend/services/agent/proposal_http.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/proposal_http.py)
