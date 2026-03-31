from __future__ import annotations

import os
from types import SimpleNamespace

import litellm
import pytest

from backend.services.agent.langfuse_litellm import (
    agent_run_litellm_metadata,
    ensure_langfuse_litellm_configured,
)
from backend.services.agent.model_client import LiteLLMModelClient


def test_agent_run_litellm_metadata_includes_optional_user_id():
    meta = agent_run_litellm_metadata(
        run_id="run-1",
        thread_id="thread-1",
        owner_user_id="user-1",
        step_index=2,
        surface="app",
    )
    assert meta["trace_id"] == "run-1"
    assert meta["session_id"] == "thread-1"
    assert meta["trace_user_id"] == "user-1"
    assert meta["generation_name"] == "agent-step-2"
    assert meta["tags"] == ["agent", "app"]


def test_agent_run_litellm_metadata_omits_user_when_none():
    meta = agent_run_litellm_metadata(
        run_id="run-1",
        thread_id="thread-1",
        owner_user_id=None,
        step_index=1,
        surface="telegram",
    )
    assert "trace_user_id" not in meta
    assert meta["tags"] == ["agent", "telegram"]


def test_ensure_langfuse_registers_litellm_callback_when_keys_present(monkeypatch: pytest.MonkeyPatch):
    import backend.services.agent.langfuse_litellm as lf_module

    monkeypatch.setitem(os.environ, "LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setitem(os.environ, "LANGFUSE_SECRET_KEY", "sk-lf-test")
    lf_module._langfuse_callback_installed = False  # noqa: SLF001
    litellm.callbacks = [c for c in litellm.callbacks if c != "langfuse_otel"]
    try:
        ensure_langfuse_litellm_configured()
        assert "langfuse_otel" in litellm.callbacks
        ensure_langfuse_litellm_configured()
        assert litellm.callbacks.count("langfuse_otel") == 1
    finally:
        litellm.callbacks = [c for c in litellm.callbacks if c != "langfuse_otel"]
        lf_module._langfuse_callback_installed = False  # noqa: SLF001


def test_complete_passes_litellm_metadata_to_litellm(monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    client = LiteLLMModelClient(
        model_name="google/gemini-3-flash-preview",
        tools=[],
        retry_max_attempts=1,
        retry_initial_wait_seconds=0.0,
        retry_max_wait_seconds=0.0,
        retry_backoff_multiplier=2.0,
    )

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="Hello", tool_calls=[]),
                )
            ],
            usage={"input_tokens": 3, "output_tokens": 2},
        )

    monkeypatch.setattr("backend.services.agent.model_client.litellm.completion", fake_completion)
    meta = agent_run_litellm_metadata(
        run_id="run-1",
        thread_id="thread-1",
        owner_user_id=None,
        step_index=1,
        surface="app",
    )
    client.complete([{"role": "user", "content": "hi"}], litellm_metadata=meta)
    assert captured.get("metadata") == meta
