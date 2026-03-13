# CALLING SPEC:
# - Purpose: implement focused service logic for `catalog`.
# - Inputs: callers that import `backend/services/agent/tool_runtime_support/catalog.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `catalog`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from collections.abc import Collection
from typing import Any

from backend.services.agent.tool_runtime_support.catalog_proposals import PROPOSAL_TOOLS
from backend.services.agent.tool_runtime_support.catalog_read import READ_TOOLS
from backend.services.agent.tool_runtime_support.catalog_session import SESSION_TOOLS
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition


TOOLS: dict[str, AgentToolDefinition] = {
    **READ_TOOLS,
    **SESSION_TOOLS,
    **PROPOSAL_TOOLS,
}


def build_openai_tool_schemas(
    *,
    tool_names: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    if tool_names is None:
        return [tool.openai_tool_schema for tool in TOOLS.values()]

    requested_names = set(tool_names)
    unknown_names = requested_names.difference(TOOLS)
    if unknown_names:
        unknown_names_text = ", ".join(sorted(unknown_names))
        raise ValueError(f"unknown tool names: {unknown_names_text}")

    return [
        tool.openai_tool_schema
        for name, tool in TOOLS.items()
        if name in requested_names
    ]
