# CALLING SPEC:
# - Purpose: implement focused service logic for `tools`.
# - Inputs: callers that import `backend/services/agent/tools.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `tools`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

"""Compatibility re-export surface for tests and external importers.

Production modules in this package should import from the owning tool_* modules
directly so there is a single canonical home for runtime and type logic.
"""

from backend.services.agent.tool_args.shared import INTERMEDIATE_UPDATE_TOOL_NAME
from backend.services.agent.tool_runtime import (
    TOOLS,
    AgentToolDefinition,
    build_openai_tool_schemas,
    execute_tool,
)
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus

__all__ = [
    "AgentToolDefinition",
    "INTERMEDIATE_UPDATE_TOOL_NAME",
    "TOOLS",
    "ToolContext",
    "ToolExecutionResult",
    "ToolExecutionStatus",
    "build_openai_tool_schemas",
    "execute_tool",
]
