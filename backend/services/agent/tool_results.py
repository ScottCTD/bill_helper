from __future__ import annotations

from typing import Any

from backend.services.agent.tool_types import ToolExecutionResult, ToolExecutionStatus


def format_lines(lines: list[str]) -> str:
    return "\n".join(lines)


def error_result(summary: str, *, details: Any | None = None) -> ToolExecutionResult:
    payload: dict[str, Any] = {"status": "ERROR", "summary": summary}
    lines = ["ERROR", f"summary: {summary}"]
    if details is not None:
        payload["details"] = details
        lines.append(f"details: {details}")
    return ToolExecutionResult(
        output_text=format_lines(lines),
        output_json=payload,
        status=ToolExecutionStatus.ERROR,
    )
