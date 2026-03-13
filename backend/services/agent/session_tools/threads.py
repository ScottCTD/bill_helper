# CALLING SPEC:
# - Purpose: implement focused service logic for `threads`.
# - Inputs: callers that import `backend/services/agent/session_tools/threads.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `threads`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from backend.services.agent.threads import (
    AgentThreadNotFoundError,
    rename_thread_for_run,
)
from backend.services.agent.tool_args.threads import RenameThreadArgs
from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.validation.agent_threads import AgentThreadTitleError


def rename_thread(context: ToolContext, args: RenameThreadArgs) -> ToolExecutionResult:
    try:
        result = rename_thread_for_run(context.db, run_id=context.run_id, title=args.title)
    except (AgentThreadNotFoundError, AgentThreadTitleError) as exc:
        return error_result(str(exc))

    output_json = {
        "status": "OK",
        "summary": f"renamed thread to {result.thread.title}",
        "thread_id": result.thread.id,
        "title": result.thread.title,
        "previous_title": result.previous_title,
    }
    return ToolExecutionResult(
        output_text="\n".join(
            [
                "OK",
                f"summary: renamed thread to {result.thread.title}",
                f"thread_id: {result.thread.id}",
                f"title: {result.thread.title}",
            ]
        ),
        output_json=output_json,
        status=ToolExecutionStatus.OK,
    )
