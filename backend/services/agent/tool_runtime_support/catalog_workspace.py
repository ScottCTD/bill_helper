# CALLING SPEC:
# - Purpose: define workspace command tool definitions for the model-visible runtime catalog.
# - Inputs: callers that import `catalog_workspace.py`.
# - Outputs: workspace-related `AgentToolDefinition` records.
# - Side effects: module-local registry construction only.
from __future__ import annotations

from backend.services.agent.tool_args.workspace_command import RunWorkspaceCommandArgs
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition
from backend.services.agent.workspace_command import run_workspace_command


WORKSPACE_TOOLS: dict[str, AgentToolDefinition] = {
    "terminal": AgentToolDefinition(
        name="terminal",
        description=(
            "Run a shell command inside the current user's workspace container. "
            "The command is executed verbatim via `bash -lc`, so multiline scripts, heredocs, pipes, redirects, "
            "and normal shell composition are allowed. "
            "Use this for local filesystem work under /workspace, read-only inspection under /data, "
            "and Bill Helper app operations through the installed `bh` executable. "
            "Prefer `bh` over raw curl or ad hoc Python when the task is about Bill Helper state. "
            "The backend injects the current run/thread/auth context automatically, and the default working directory is /workspace/workspace."
        ),
        args_model=RunWorkspaceCommandArgs,
        handler=run_workspace_command,
    ),
}
