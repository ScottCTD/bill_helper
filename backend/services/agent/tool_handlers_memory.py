from __future__ import annotations

from backend.services.agent.tool_args.memory import AddUserMemoryArgs
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult, ToolExecutionStatus
from backend.services.runtime_settings import append_user_memory_items


def _format_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def add_user_memory(context: ToolContext, args: AddUserMemoryArgs) -> ToolExecutionResult:
    added_items, all_items = append_user_memory_items(
        context.db,
        items=args.memory_items,
    )
    payload = {
        "status": "OK",
        "summary": f"added {len(added_items)} memory item(s)",
        "added_count": len(added_items),
        "added_items": added_items,
        "total_count": len(all_items),
        "all_items": all_items,
    }
    return ToolExecutionResult(
        output_text=_format_lines(
            [
                "OK",
                f"summary: added {len(added_items)} memory item(s)",
                f"added_items: {added_items or '(none)'}",
                f"total_count: {len(all_items)}",
            ]
        ),
        output_json=payload,
        status=ToolExecutionStatus.OK,
    )
