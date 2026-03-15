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
    "run_workspace_command": AgentToolDefinition(
        name="run_workspace_command",
        description=(
            "Run a shell command inside the current user's workspace container. "
            "Use this for local filesystem work under /workspace, read-only inspection under /data, "
            "and Bill Helper app operations through the installed `bh` executable. "
            "Prefer `bh` over raw curl or ad hoc Python when the task is about Bill Helper state. "
            "The backend injects the current run/thread/auth context automatically."
        ),
        args_model=RunWorkspaceCommandArgs,
        handler=run_workspace_command,
    ),
}
