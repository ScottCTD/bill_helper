# CALLING SPEC:
# - Purpose: implement focused service logic for `catalog_session`.
# - Inputs: callers that import `backend/services/agent/tool_runtime_support/catalog_session.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `catalog_session`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from backend.services.agent.session_tools.memory import add_user_memory
from backend.services.agent.session_tools.progress import send_intermediate_update
from backend.services.agent.session_tools.threads import rename_thread
from backend.services.agent.tool_args.memory import AddUserMemoryArgs
from backend.services.agent.tool_args.shared import (
    INTERMEDIATE_UPDATE_TOOL_NAME,
    SendIntermediateUpdateArgs,
)
from backend.services.agent.tool_args.threads import RenameThreadArgs
from backend.services.agent.tool_runtime_support.definitions import AgentToolDefinition


SESSION_TOOLS: dict[str, AgentToolDefinition] = {
    "add_user_memory": AgentToolDefinition(
        name="add_user_memory",
        description=(
            "Append new persistent user-memory items. Use this only when the user clearly asks you "
            "to remember/store a standing preference, rule, or hint for future runs. This tool is "
            "add-only: do not use it to mutate or remove existing memory."
        ),
        args_model=AddUserMemoryArgs,
        handler=add_user_memory,
    ),
    "rename_thread": AgentToolDefinition(
        name="rename_thread",
        description=(
            "Rename the current thread to a short 1-5 word topic. Use this right after the first user "
            "message in a new thread. After that, only rename when the user explicitly asks or the topic "
            "shifts substantially."
        ),
        args_model=RenameThreadArgs,
        handler=rename_thread,
    ),
    INTERMEDIATE_UPDATE_TOOL_NAME: AgentToolDefinition(
        name=INTERMEDIATE_UPDATE_TOOL_NAME,
        description=(
            "Call this tool before calling other tools (but after rename_thread). "
            "Call this tool again only for meaningful transitions between tool calls; "
            "do not call it on every tool step."
        ),
        args_model=SendIntermediateUpdateArgs,
        handler=send_intermediate_update,
    ),
}
