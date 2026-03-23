from __future__ import annotations

from backend.services.agent.runtime_state import PreparedToolCall, tool_result_llm_message
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


def test_tool_result_llm_message_uses_structured_llm_content_when_present() -> None:
    result = ToolExecutionResult(
        output_text="OK\nsummary: loaded 1 image",
        output_json={"summary": "loaded 1 image"},
        status=ToolExecutionStatus.OK,
        llm_content=[
            {"type": "text", "text": "Loaded one image."},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
        ],
    )

    message = tool_result_llm_message(
        PreparedToolCall(
            tool_call={"id": "call_1"},
            tool_name="read_image",
            arguments={},
        ),
        result,
    )

    assert message["role"] == "tool"
    assert message["tool_call_id"] == "call_1"
    assert isinstance(message["content"], list)
    assert message["content"][0]["type"] == "text"
    assert message["content"][1]["type"] == "image_url"
