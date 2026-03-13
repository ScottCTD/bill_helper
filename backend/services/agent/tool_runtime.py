# CALLING SPEC:
# - Purpose: implement focused service logic for `tool_runtime`.
# - Inputs: callers that import `backend/services/agent/tool_runtime.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `tool_runtime`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

"""Stable public seam for tool runtime contracts and execution."""

from backend.services.agent.tool_runtime_support.catalog import (
    TOOLS,
    build_openai_tool_schemas,
)
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition
from backend.services.agent.tool_runtime_support.execution import execute_tool

__all__ = [
    "AgentToolDefinition",
    "TOOLS",
    "build_openai_tool_schemas",
    "execute_tool",
]
