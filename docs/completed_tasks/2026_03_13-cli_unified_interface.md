# CLI As Unified App Interface

## Outcome

Bill Helper now uses the `billengine` CLI as the primary app-operation interface inside the agent workspace container.

At the model-visible runtime boundary, the old direct CRUD/read tool catalog was replaced with:

- `terminal`
- `send_intermediate_update`
- `rename_thread`
- `add_user_memory`

The agent now performs Bill Helper reads, proposal lifecycle operations, and review actions by invoking `billengine` inside the workspace terminal.

## Implemented Scope

- Added the `billengine` console entry point in [backend/cli/main.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/cli/main.py) and supporting helpers in [backend/cli/support.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/cli/support.py).
- Added thread-scoped proposal HTTP routes in [backend/routers/agent_proposals.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/routers/agent_proposals.py) backed by [backend/services/agent/proposal_http.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/proposal_http.py).
- Added the workspace terminal tool in [backend/services/agent/workspace_command.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/workspace_command.py) plus its catalog/arg wiring.
- Reduced the model-visible tool catalog in [backend/services/agent/tool_runtime_support/catalog.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/agent/tool_runtime_support/catalog.py).
- Updated Docker workspace execution support in [backend/services/docker_cli.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/docker_cli.py) and [docker/agent-workspace.dockerfile](/Users/scottcui/.codex/worktrees/479c/bill_helper/docker/agent-workspace.dockerfile) so the image includes the package and `billengine`.
- Fixed workspace session expiry comparison in [backend/services/sessions.py](/Users/scottcui/.codex/worktrees/479c/bill_helper/backend/services/sessions.py) so workspace-minted temporary bearer tokens work reliably against SQLite datetime values.

## Current CLI Surface

The implemented CLI covers:

- `status`
- `threads list|show|create|rename`
- `entries list|get`
- `accounts list|snapshots|reconciliation`
- `groups list|get`
- `entities list`
- `tags list`
- `proposals list|get|create|update|remove`
- `reviews approve|reject|reopen`
- `workspace status`

`billengine` remains a thin HTTP client. Canonical mutations still happen only through backend review/apply flows.

## Verification

- `uv run python -m py_compile` on touched Python modules
- `OPENROUTER_API_KEY=test uv run pytest backend/tests/test_auth_sessions.py backend/tests/test_agent_cli_proposals.py backend/tests/test_workspace_command.py -q`
- `uv run python scripts/check_llm_design.py`
- `uv run python scripts/check_docs_sync.py`
- direct `billengine` execution inside the workspace container against a disposable backend
- headed Playwright browser validation of the proposal and approval flow against a disposable backend

## Related Stable Docs

- [docs/features/agent_cli_workspace.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/docs/features/agent_cli_workspace.md)
- [docs/agent_billing_assistant.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/docs/agent_billing_assistant.md)
- [docs/api/agent.md](/Users/scottcui/.codex/worktrees/479c/bill_helper/docs/api/agent.md)
