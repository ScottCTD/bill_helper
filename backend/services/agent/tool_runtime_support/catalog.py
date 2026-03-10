from __future__ import annotations

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


def build_openai_tool_schemas() -> list[dict[str, Any]]:
    return [tool.openai_tool_schema for tool in TOOLS.values()]
