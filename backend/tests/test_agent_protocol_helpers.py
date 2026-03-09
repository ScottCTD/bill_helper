from __future__ import annotations

from backend.services.agent.protocol_helpers import canonicalize_tool_call, decode_tool_call


def test_decode_tool_call_surfaces_argument_decode_error() -> None:
    decoded = decode_tool_call(
        {
            "id": "call_list_tags",
            "type": "function",
            "function": {"name": "list_tags", "arguments": "{"},
        }
    )

    assert decoded.tool_name == "list_tags"
    assert decoded.arguments == {}
    assert decoded.raw_arguments == "{"
    assert decoded.decode_error == "arguments are not valid JSON"


def test_canonicalize_tool_call_preserves_raw_arguments_on_decode_error() -> None:
    canonical = canonicalize_tool_call(
        {
            "id": "call_list_tags",
            "type": "function",
            "function": {"name": "list_tags", "arguments": "{"},
        }
    )

    assert canonical["function"]["name"] == "list_tags"
    assert canonical["function"]["arguments"] == "{"
