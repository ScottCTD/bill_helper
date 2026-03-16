# CALLING SPEC:
# - Purpose: define terminal tool definitions for the model-visible runtime catalog.
# - Inputs: callers that import `catalog_terminal.py`.
# - Outputs: terminal-related `AgentToolDefinition` records.
# - Side effects: module-local registry construction only.
from __future__ import annotations

from backend.services.agent.tool_args.terminal import RunTerminalArgs
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition
from backend.services.agent.terminal import run_terminal


TERMINAL_TOOLS: dict[str, AgentToolDefinition] = {
    "terminal": AgentToolDefinition(
        name="terminal",
        description=(
            "Use this tool for shell work inside the current user's workspace container. "
            "Use `bh` for Bill Helper app operations, standard shell commands for local work under /workspace, "
            "and read-only inspection under /data. "
            "Use `bh` when the task is about the Bill Helper app. "
        ),
        args_model=RunTerminalArgs,
        handler=run_terminal,
    ),
}
