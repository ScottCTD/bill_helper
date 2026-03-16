from __future__ import annotations

import os
from types import SimpleNamespace

import litellm
import pytest

from backend.services.agent.model_client import AgentModelError, LiteLLMModelClient, validate_litellm_environment


def _build_model_client(
    *,
    retry_max_attempts: int = 3,
) -> LiteLLMModelClient:
    return LiteLLMModelClient(
        model_name="google/gemini-3-flash-preview",
        tools=[],
        retry_max_attempts=retry_max_attempts,
        retry_initial_wait_seconds=0.0,
        retry_max_wait_seconds=0.0,
        retry_backoff_multiplier=2.0,
    )


def test_complete_stream_retries_before_first_text_delta(monkeypatch):
    client = _build_model_client(retry_max_attempts=2)
    calls = {"count": 0}
    responses: list[object] = [
        RuntimeError("Connection error."),
        iter(
            [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {}}], "usage": {"input_tokens": 2, "output_tokens": 1}},
            ]
        ),
    ]

    def fake_completion(**_kwargs):
        calls["count"] += 1
        next_response = responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    events = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert calls["count"] == 2
    assert [event["type"] for event in events] == ["text_delta", "done"]
    assert events[0]["delta"] == "Hello"
    assert events[1]["message"]["content"] == "Hello"
    assert events[1]["message"]["usage"]["input_tokens"] == 2
    assert events[1]["message"]["usage"]["output_tokens"] == 1


def test_complete_stream_retries_transient_ssl_bad_record_mac_when_max_attempts_is_one(monkeypatch):
    client = _build_model_client(retry_max_attempts=1)
    calls = {"count": 0}

    def fake_completion(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise litellm.APIError(
                500,
                "OpenrouterException - [SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac",
                "openrouter",
                "openrouter/google/gemini-2.5-flash",
            )
        return iter(
            [
                {"choices": [{"delta": {"content": "Hello"}}]},
                {"choices": [{"delta": {}}], "usage": {"input_tokens": 2, "output_tokens": 1}},
            ]
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    events = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert calls["count"] == 2
    assert [event["type"] for event in events] == ["text_delta", "done"]
    assert events[0]["delta"] == "Hello"
    assert events[1]["message"]["content"] == "Hello"
    assert events[1]["message"]["usage"]["input_tokens"] == 2
    assert events[1]["message"]["usage"]["output_tokens"] == 1


def test_complete_stream_emits_reasoning_delta_events(monkeypatch):
    client = _build_model_client(retry_max_attempts=1)

    def fake_completion(**_kwargs):
        return iter(
            [
                {"choices": [{"delta": {"reasoning_content": "Checking "}}]},
                {"choices": [{"delta": {"reasoning_content": "entities"}}]},
                {"choices": [{"delta": {"content": "Done."}}]},
                {
                    "choices": [{"delta": {}}],
                    "usage": {"input_tokens": 3, "output_tokens": 1},
                },
            ]
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    events = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert [event["type"] for event in events] == [
        "reasoning_delta",
        "reasoning_delta",
        "text_delta",
        "done",
    ]
    assert events[0]["delta"] == "Checking "
    assert events[1]["delta"] == "entities"
    assert events[2]["delta"] == "Done."
    assert events[3]["message"]["reasoning"] == "Checking entities"
    assert events[3]["message"]["content"] == "Done."


def test_complete_stream_merges_cumulative_tool_call_deltas_without_corrupting_arguments(monkeypatch):
    client = _build_model_client(retry_max_attempts=1)

    def fake_completion(**_kwargs):
        return iter(
            [
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                    {
                                            "index": 0,
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {
                                                "name": "ter",
                                                "arguments": '{"command":"bh',
                                            },
                                        }
                                    ]
                            }
                        }
                    ]
                },
                {
                    "choices": [
                        {
                            "delta": {
                                "tool_calls": [
                                        {
                                            "index": 0,
                                            "function": {
                                                "name": "terminal",
                                                "arguments": '{"command":"bh tags list"}',
                                            },
                                        }
                                    ]
                            }
                        }
                    ]
                },
                {"choices": [{"delta": {}}], "usage": {"input_tokens": 2, "output_tokens": 1}},
            ]
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    events = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert [event["type"] for event in events] == ["done"]
    assert events[0]["message"]["tool_calls"] == [
        {
            "id": "call_1",
            "type": "function",
                "function": {
                    "name": "terminal",
                    "arguments": '{"command":"bh tags list"}',
                },
            }
        ]


def test_complete_retries_before_failing(monkeypatch):
    client = _build_model_client(retry_max_attempts=2)
    calls = {"count": 0}

    def fake_completion(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Connection error.")
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    response = client.complete([{"role": "user", "content": "hi"}])

    assert calls["count"] == 2
    assert response["content"] == "Hello"
    assert response["usage"]["input_tokens"] == 3
    assert response["usage"]["output_tokens"] == 2


def test_complete_omits_tool_fields_when_explicit_tools_override_is_empty(monkeypatch):
    captured_request: dict[str, object] = {}
    client = LiteLLMModelClient(
        model_name="google/gemini-3-flash-preview",
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "terminal",
                    "description": "List entries",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        retry_max_attempts=1,
        retry_initial_wait_seconds=0.0,
        retry_max_wait_seconds=0.0,
        retry_backoff_multiplier=2.0,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    response = client.complete([{"role": "user", "content": "hi"}], tools=[])

    assert response["content"] == "Hello"
    assert "tools" not in captured_request
    assert "tool_choice" not in captured_request


def test_complete_passes_response_format_when_provided(monkeypatch):
    captured_request: dict[str, object] = {}
    client = _build_model_client(retry_max_attempts=1)
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "demo",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "value": {"type": "string"},
                },
                "required": ["value"],
            },
        },
    }

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"value":"ok"}',
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    response = client.complete(
        [{"role": "user", "content": "hi"}],
        response_format=response_format,
    )

    assert response["content"] == '{"value":"ok"}'
    assert captured_request["response_format"] == response_format


def test_complete_retries_transient_ssl_bad_record_mac_when_max_attempts_is_one(monkeypatch):
    client = _build_model_client(retry_max_attempts=1)
    calls = {"count": 0}

    def fake_completion(**_kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise litellm.APIError(
                500,
                "OpenrouterException - [SSL: SSLV3_ALERT_BAD_RECORD_MAC] sslv3 alert bad record mac",
                "openrouter",
                "openrouter/google/gemini-2.5-flash",
            )
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    response = client.complete([{"role": "user", "content": "hi"}])

    assert calls["count"] == 2
    assert response["content"] == "Hello"
    assert response["usage"]["input_tokens"] == 3
    assert response["usage"]["output_tokens"] == 2


def test_complete_injects_prompt_cache_control_points_when_supported(monkeypatch):
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    monkeypatch.setattr(
        "backend.services.agent.model_client.litellm.utils.supports_prompt_caching",
        lambda _model: True,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    client.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "hello"},
        ]
    )

    assert captured_request["cache_control_injection_points"] == [
        {"location": "message", "index": 0},
        {"location": "message", "index": -1},
    ]


def test_complete_injects_boundary_before_latest_assistant_tool_batch(monkeypatch):
    """First tool-loop iteration: boundary is the user message (just before assistant)."""
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    monkeypatch.setattr(
        "backend.services.agent.model_client.litellm.utils.supports_prompt_caching",
        lambda _model: True,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    client.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Please process this receipt."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "list_entities", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "name": "list_entities", "content": "OK"},
        ]
    )

    assert captured_request["cache_control_injection_points"] == [
        {"location": "message", "index": 0},
        {"location": "message", "index": -3},
        {"location": "message", "index": -1},
    ]


def test_complete_injects_boundary_at_prev_tool_result_in_continued_loop(monkeypatch):
    """Second tool-loop iteration: boundary is the previous iteration's last tool result."""
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    monkeypatch.setattr(
        "backend.services.agent.model_client.litellm.utils.supports_prompt_caching",
        lambda _model: True,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hello", tool_calls=[])
                )
            ],
            usage={"input_tokens": 5, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    client.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Process receipt."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "list_entities", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "c1", "name": "list_entities", "content": "OK"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c2", "type": "function", "function": {"name": "list_tags", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "c2", "name": "list_tags", "content": "OK"},
        ]
    )

    # Boundary at index 3 (tool result from iter 1) = -3, last message = -1
    assert captured_request["cache_control_injection_points"] == [
        {"location": "message", "index": 0},
        {"location": "message", "index": -3},
        {"location": "message", "index": -1},
    ]


def test_complete_injects_second_to_last_user_for_multi_turn(monkeypatch):
    """New turn with history: second-to-last user message enables cross-turn cache reuse."""
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    monkeypatch.setattr(
        "backend.services.agent.model_client.litellm.utils.supports_prompt_caching",
        lambda _model: True,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hello", tool_calls=[])
                )
            ],
            usage={"input_tokens": 5, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    client.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer"},
            {"role": "user", "content": "Second question"},
        ]
    )

    # Second-to-last user = index 1 = -3, last message = -1
    assert captured_request["cache_control_injection_points"] == [
        {"location": "message", "index": 0},
        {"location": "message", "index": -3},
        {"location": "message", "index": -1},
    ]


def test_complete_tool_loop_with_multiple_tool_results(monkeypatch):
    """Tool loop with parallel tool calls: boundary still before the assistant."""
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    monkeypatch.setattr(
        "backend.services.agent.model_client.litellm.utils.supports_prompt_caching",
        lambda _model: True,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Done", tool_calls=[])
                )
            ],
            usage={"input_tokens": 5, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    client.complete(
        [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Process receipt."},
            {"role": "assistant", "content": "", "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "list_entities", "arguments": "{}"}},
                {"id": "c2", "type": "function", "function": {"name": "list_tags", "arguments": "{}"}},
            ]},
            {"role": "tool", "tool_call_id": "c1", "name": "list_entities", "content": "OK"},
            {"role": "tool", "tool_call_id": "c2", "name": "list_tags", "content": "OK"},
        ]
    )

    # Boundary at user (index 1) = -4, last tool result = -1
    assert captured_request["cache_control_injection_points"] == [
        {"location": "message", "index": 0},
        {"location": "message", "index": -4},
        {"location": "message", "index": -1},
    ]


def test_complete_does_not_inject_prompt_cache_control_for_short_message_lists(monkeypatch):
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    monkeypatch.setattr(
        "backend.services.agent.model_client.litellm.utils.supports_prompt_caching",
        lambda _model: True,
    )

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    client.complete([{"role": "user", "content": "hello"}])

    assert "cache_control_injection_points" not in captured_request


def test_complete_normalizes_top_level_prompt_cache_usage_fields(monkeypatch):
    client = _build_model_client()

    def fake_completion(**_kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={
                "input_tokens": 120,
                "output_tokens": 15,
                "cache_read_input_tokens": 80,
                "cache_creation_input_tokens": 20,
            },
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    response = client.complete([{"role": "user", "content": "hello"}])

    assert response["usage"]["input_tokens"] == 120
    assert response["usage"]["output_tokens"] == 15
    assert response["usage"]["cache_read_tokens"] == 80
    assert response["usage"]["cache_write_tokens"] == 20


def test_complete_omits_observability_fields(monkeypatch):
    captured_request: dict[str, object] = {}
    client = _build_model_client()

    def fake_completion(**kwargs):
        captured_request.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Hello",
                        tool_calls=[],
                    )
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    response = client.complete([{"role": "user", "content": "hello"}])

    assert "metadata" not in captured_request
    assert "extra_body" not in captured_request
    assert "langfuse_public_key" not in captured_request
    assert "langfuse_secret_key" not in captured_request
    assert "langfuse_host" not in captured_request
    assert response["content"] == "Hello"


def test_complete_stream_retries_after_partial_text_delta_without_duplicate_output(monkeypatch):
    client = _build_model_client(retry_max_attempts=3)
    calls = {"count": 0}

    def broken_stream():
        yield {"choices": [{"delta": {"content": "Hel"}}]}
        raise RuntimeError("Connection error.")

    responses: list[object] = [
        broken_stream(),
        iter(
            [
                {"choices": [{"delta": {"content": "Hel"}}]},
                {"choices": [{"delta": {"content": "lo"}}]},
                {"choices": [{"delta": {}}], "usage": {"input_tokens": 2, "output_tokens": 1}},
            ]
        ),
    ]

    def fake_completion(**_kwargs):
        calls["count"] += 1
        next_response = responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    events = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert calls["count"] == 2
    assert [event["type"] for event in events] == ["text_delta", "text_delta", "done"]
    assert events[0]["delta"] == "Hel"
    assert events[1]["delta"] == "lo"
    assert events[2]["message"]["content"] == "Hello"


def test_complete_stream_fails_when_retry_output_diverges_after_emitted_text(monkeypatch):
    client = _build_model_client(retry_max_attempts=2)
    calls = {"count": 0}

    def first_attempt():
        yield {"choices": [{"delta": {"content": "Hel"}}]}
        raise RuntimeError("Connection error.")

    def second_attempt():
        yield {"choices": [{"delta": {"content": "Hex"}}]}

    responses: list[object] = [
        first_attempt(),
        second_attempt(),
    ]

    def fake_completion(**_kwargs):
        calls["count"] += 1
        next_response = responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    stream = client.complete_stream([{"role": "user", "content": "hi"}])

    first_event = next(stream)
    assert first_event["type"] == "text_delta"
    assert first_event["delta"] == "Hel"

    with pytest.raises(AgentModelError, match="divergent output"):
        next(stream)
    assert calls["count"] == 2


def test_complete_stream_replay_prefix_is_suppressed_across_retries(monkeypatch):
    client = _build_model_client(retry_max_attempts=2)
    calls = {"count": 0}

    def first_attempt():
        yield {"choices": [{"delta": {"content": "Hello"}}]}
        raise RuntimeError("Connection error.")

    def second_attempt():
        yield {"choices": [{"delta": {"content": "Hel"}}]}
        yield {"choices": [{"delta": {"content": "lo"}}]}
        yield {"choices": [{"delta": {"content": " world"}}]}
        yield {"choices": [{"delta": {}}], "usage": {"input_tokens": 4, "output_tokens": 2}}

    responses: list[object] = [
        first_attempt(),
        second_attempt(),
    ]

    def fake_completion(**_kwargs):
        calls["count"] += 1
        next_response = responses.pop(0)
        if isinstance(next_response, Exception):
            raise next_response
        return next_response

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    events = list(client.complete_stream([{"role": "user", "content": "hi"}]))

    assert calls["count"] == 2
    assert [event["type"] for event in events] == ["text_delta", "text_delta", "done"]
    assert events[0]["delta"] == "Hello"
    assert events[1]["delta"] == " world"
    assert events[2]["message"]["content"] == "Hello world"


def test_validate_litellm_environment_allows_indeterminate_validation(monkeypatch):
    def failing_validate_environment(**_kwargs):
        raise RuntimeError("unexpected provider config")

    monkeypatch.setattr(litellm, "validate_environment", failing_validate_environment)
    has_credentials, missing_keys, request_model = validate_litellm_environment(
        model_name="openai/gpt-4.1-mini",
    )

    assert has_credentials is True
    assert missing_keys == []
    assert request_model == "openai/gpt-4.1-mini"


def test_validate_litellm_environment_accepts_bedrock_bearer_token(monkeypatch):
    monkeypatch.setattr("backend.config._env_files", ())
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "ABSK-test-token")
    monkeypatch.setattr(
        litellm,
        "validate_environment",
        lambda **_kwargs: {
            "keys_in_environment": False,
            "missing_keys": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        },
    )

    has_credentials, missing_keys, request_model = validate_litellm_environment(
        model_name="bedrock/anthropic.claude-sonnet-4-6",
    )

    assert has_credentials is True
    assert missing_keys == []
    assert request_model == "bedrock/anthropic.claude-sonnet-4-6"


def test_validate_litellm_environment_loads_bedrock_bearer_token_from_env_file(
    monkeypatch, tmp_path
):
    env_file = tmp_path / ".env"
    env_file.write_text("AWS_BEARER_TOKEN_BEDROCK=ABSK-test-token\n", encoding="utf-8")
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.setattr("backend.config._env_files", (str(env_file),))
    monkeypatch.setattr(
        litellm,
        "validate_environment",
        lambda **_kwargs: {
            "keys_in_environment": False,
            "missing_keys": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        },
    )

    has_credentials, missing_keys, request_model = validate_litellm_environment(
        model_name="bedrock/anthropic.claude-sonnet-4-6",
    )

    assert has_credentials is True
    assert missing_keys == []
    assert request_model == "bedrock/anthropic.claude-sonnet-4-6"
    assert os.environ["AWS_BEARER_TOKEN_BEDROCK"] == "ABSK-test-token"


def test_validate_litellm_environment_reports_bedrock_bearer_token_alternative(
    monkeypatch,
):
    monkeypatch.setattr("backend.config._env_files", ())
    monkeypatch.delenv("AWS_BEARER_TOKEN_BEDROCK", raising=False)
    monkeypatch.setattr(
        litellm,
        "validate_environment",
        lambda **_kwargs: {
            "keys_in_environment": False,
            "missing_keys": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
        },
    )

    has_credentials, missing_keys, _request_model = validate_litellm_environment(
        model_name="bedrock/anthropic.claude-sonnet-4-6",
    )

    assert has_credentials is False
    assert missing_keys == [
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_BEARER_TOKEN_BEDROCK",
    ]
