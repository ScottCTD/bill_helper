from __future__ import annotations

from backend.services.agent.tool_types import ToolExecutionResult, ToolExecutionStatus


def test_tool_execution_result_canonicalizes_output_json_status_to_enum_value() -> None:
    result = ToolExecutionResult(
        output_text="OK\nsummary: test",
        output_json={"status": "OK", "summary": "test"},
        status=ToolExecutionStatus.OK,
    )

    assert result.status == ToolExecutionStatus.OK
    assert result.output_json["status"] == "ok"


def test_tool_execution_result_adds_status_when_output_json_omits_it() -> None:
    result = ToolExecutionResult(
        output_text="ERROR\nsummary: failed",
        output_json={"summary": "failed"},
        status=ToolExecutionStatus.ERROR,
    )

    assert result.status == ToolExecutionStatus.ERROR
    assert result.output_json["status"] == "error"
