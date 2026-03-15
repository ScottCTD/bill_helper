# Billing Assistant Agent

This document describes the current Bill Helper agent architecture at a high level.

For the detailed CLI/workspace execution model, see [docs/features/agent_cli_workspace.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/docs/features/agent_cli_workspace.md).

## What The Agent Is

Bill Helper uses a review-gated agent:

- users send messages in an owner-scoped thread
- the model can read Bill Helper state and the workspace filesystem
- any create, update, or delete must become a proposal first
- a human approves, rejects, or reopens proposals before domain tables change

The agent no longer receives the old large direct CRUD tool catalog. The model-visible surface is now intentionally small:

- `run_workspace_command`
- `send_intermediate_update`
- `rename_thread`
- `add_user_memory`

`run_workspace_command` is the main execution primitive. Inside the workspace container, the agent uses the installed `billengine` CLI for Bill Helper reads, proposal lifecycle operations, and review actions.

## User Flow

1. Open the Agent workspace in the app.
2. Create or select a thread.
3. Send a prompt and optional attachments.
4. Watch run progress in the timeline, including intermediate updates and tool activity.
5. Open the thread review modal when proposals are ready.
6. Approve, reject, reopen, or batch-process proposals.
7. Applied proposals mutate the real owner-scoped domain data.

## Runtime Shape

The runtime still follows the same core loop:

1. persist the user message and create a run
2. build the system prompt plus thread history and current-user context
3. call the model
4. execute tool calls
5. append tool results and continue until completion or `agent_max_steps`
6. persist the final assistant message and any proposals

What changed is the execution boundary:

- before: the model chose among many specialized backend CRUD/read tools
- now: the model primarily uses one workspace terminal tool plus `billengine`

That reduction saves prompt/tool-schema context and makes the app behavior easier to extend without expanding the model-visible catalog.

## Workspace And CLI Model

The workspace container receives execution env on every terminal call:

- `BILLENGINE_API_BASE_URL`
- `BILLENGINE_AUTH_TOKEN`
- `BILLENGINE_THREAD_ID`
- `BILLENGINE_RUN_ID`
- `BILLENGINE_WORKSPACE_ROOT`
- `BILLENGINE_DATA_ROOT`

The injected auth token is a short-lived backend session minted for that invocation and revoked after command completion.

The `billengine` CLI is a thin HTTP client. It does not write the database directly. It calls backend routes for:

- reads such as threads, entries, accounts, groups, entities, tags, and workspace status
- thread-scoped proposal list/get/create/update/remove
- review approve/reject/reopen actions

## Review-Gated Mutation Contract

The review gate is unchanged:

- proposal creation records `AgentChangeItem` rows only
- review actions update proposal status and optionally apply reviewer overrides
- only approval apply handlers mutate domain tables

This means the CLI consolidation replaces the old model-visible CRUD tools without removing the review boundary.

## What Replaced The Legacy CRUD Tool Surface

The old direct model-visible CRUD/read tools are no longer part of the runtime catalog exposed to the model.

What remains internally:

- proposal handlers
- read helpers
- patching/normalization code
- review/apply workflows

Those modules now serve backend APIs and the `billengine` CLI instead of being exposed directly as first-class model tools.

## Key Files

- [backend/services/agent/system_prompt.j2](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/system_prompt.j2)
- [backend/services/agent/tool_runtime_support/catalog.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/tool_runtime_support/catalog.py)
- [backend/services/agent/tool_runtime_support/catalog_workspace.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/tool_runtime_support/catalog_workspace.py)
- [backend/services/agent/workspace_command.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/workspace_command.py)
- [backend/cli/main.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/cli/main.py)
- [backend/services/agent/proposal_http.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/proposal_http.py)
- [backend/routers/agent_proposals.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/routers/agent_proposals.py)

## Related Docs

- [docs/features/agent_cli_workspace.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/docs/features/agent_cli_workspace.md)
- [docs/api/agent.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/docs/api/agent.md)
- [backend/docs/agent_subsystem.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/docs/agent_subsystem.md)
