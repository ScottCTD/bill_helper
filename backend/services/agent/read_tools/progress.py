from __future__ import annotations

from backend.services.agent.tool_args import SendIntermediateUpdateArgs
from backend.services.agent.tool_results import format_lines
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus


def send_intermediate_update(_: ToolContext, args: SendIntermediateUpdateArgs) -> ToolExecutionResult:
    payload = {
        "status": "OK",
        "summary": "intermediate update shared",
        "message": args.message,
    }
    return ToolExecutionResult(
        output_text=format_lines(
            [
                "OK",
                "summary: intermediate update shared",
                f"message: {args.message}",
            ]
        ),
        output_json=payload,
        status=ToolExecutionStatus.OK,
    )
