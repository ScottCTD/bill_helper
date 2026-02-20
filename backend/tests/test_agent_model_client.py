from __future__ import annotations

from types import SimpleNamespace

import litellm
import pytest

from backend.services.agent.model_client import AgentModelError, LiteLLMModelClient, validate_litellm_environment


def _build_model_client(
    *,
    retry_max_attempts: int = 3,
    langfuse_public_key: str | None = None,
    langfuse_secret_key: str | None = None,
    langfuse_host: str | None = None,
) -> LiteLLMModelClient:
    return LiteLLMModelClient(
        model_name="google/gemini-3-flash-preview",
        tools=[],
        retry_max_attempts=retry_max_attempts,
        retry_initial_wait_seconds=0.0,
        retry_max_wait_seconds=0.0,
        retry_backoff_multiplier=2.0,
        langfuse_public_key=langfuse_public_key,
        langfuse_secret_key=langfuse_secret_key,
        langfuse_host=langfuse_host,
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


def test_complete_includes_langfuse_metadata(monkeypatch):
    captured_request: dict[str, object] = {}
    client = _build_model_client(
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_host="https://cloud.langfuse.com/",
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
    response = client.complete(
        [{"role": "user", "content": "hello"}],
        observability={
            "user": "scott",
            "session_id": "thread-1",
            "trace": {
                "trace_id": "run-1",
                "trace_name": "Bill Helper Agent Run",
                "generation_name": "agent_turn",
                "thread_id": "thread-1",
                "run_id": "run-1",
            },
        },
    )

    metadata = captured_request.get("metadata")
    assert isinstance(metadata, dict)
    assert metadata["trace_user_id"] == "scott"
    assert metadata["session_id"] == "thread-1"
    assert metadata["trace_id"] == "run-1"
    assert metadata["generation_name"] == "agent_turn"
    assert metadata["trace_metadata"] == {"thread_id": "thread-1", "run_id": "run-1"}
    assert captured_request["langfuse_public_key"] == "pk-test"
    assert captured_request["langfuse_secret_key"] == "sk-test"
    assert captured_request["langfuse_host"] == "https://cloud.langfuse.com"
    assert response["content"] == "Hello"


def test_complete_uses_step_based_generation_name_and_existing_trace_id(monkeypatch):
    """Thread-scoped trace: one trace per thread, per-run generation names, existing_trace_id for step>1 or subsequent runs."""
    captured_request: dict[str, object] = {}
    client = _build_model_client(
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )

    def fake_completion(**kwargs):
        captured_request.clear()
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

    # First run in thread, step 1: trace_id=thread_id creates trace
    client.complete(
        [{"role": "user", "content": "hello"}],
        observability={
            "user": "u1",
            "session_id": "t1",
            "trace": {
                "trace_id": "t1",
                "trace_name": "Bill Helper Agent",
                "thread_id": "t1",
                "run_id": "run-1",
                "step": 1,
                "is_first_run_in_thread": True,
                "run_index": 1,
            },
        },
    )
    meta = captured_request.get("metadata")
    assert isinstance(meta, dict)
    assert meta.get("trace_id") == "t1"
    assert "existing_trace_id" not in meta
    assert meta.get("generation_name") == "agent_turn_run_1_step_1"

    # First run, step 2: existing_trace_id continues within same run
    client.complete(
        [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "Hi"}],
        observability={
            "user": "u1",
            "session_id": "t1",
            "trace": {
                "trace_id": "t1",
                "trace_name": "Bill Helper Agent",
                "thread_id": "t1",
                "run_id": "run-1",
                "step": 2,
                "is_first_run_in_thread": True,
                "run_index": 1,
            },
        },
    )
    meta = captured_request.get("metadata")
    assert isinstance(meta, dict)
    assert meta.get("existing_trace_id") == "t1"
    assert meta.get("generation_name") == "agent_turn_run_1_step_2"

    # Second run in thread, step 1: existing_trace_id continues trace from prior run
    client.complete(
        [{"role": "user", "content": "follow-up"}],
        observability={
            "user": "u1",
            "session_id": "t1",
            "trace": {
                "trace_id": "t1",
                "trace_name": "Bill Helper Agent",
                "thread_id": "t1",
                "run_id": "run-2",
                "step": 1,
                "is_first_run_in_thread": False,
                "run_index": 2,
            },
        },
    )
    meta = captured_request.get("metadata")
    assert isinstance(meta, dict)
    assert meta.get("existing_trace_id") == "t1"
    assert meta.get("generation_name") == "agent_turn_run_2_step_1"


def test_langfuse_callbacks_are_enabled_with_langfuse_credentials(monkeypatch):
    monkeypatch.setattr(litellm, "success_callback", [], raising=False)
    monkeypatch.setattr(litellm, "failure_callback", [], raising=False)

    _build_model_client(
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )
    _build_model_client(
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
    )

    assert litellm.success_callback.count("langfuse") == 1
    assert litellm.failure_callback.count("langfuse") == 1


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
