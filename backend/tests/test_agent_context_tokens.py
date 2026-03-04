from __future__ import annotations


def test_count_context_tokens_returns_litellm_count(monkeypatch):
    from backend.services.agent.context_tokens import count_context_tokens

    captured: dict[str, object] = {}

    def fake_token_counter(**kwargs):
        captured.update(kwargs)
        return 42

    monkeypatch.setattr("backend.services.agent.context_tokens.litellm.token_counter", fake_token_counter)

    result = count_context_tokens(
        model_name="gpt-test",
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function"}],
    )

    assert result == 42
    assert captured == {
        "model": "gpt-test",
        "messages": [{"role": "user", "content": "hello"}],
        "tools": [{"type": "function"}],
        "use_default_image_token_count": True,
    }


def test_count_context_tokens_returns_none_when_tokenization_fails(monkeypatch):
    from backend.services.agent.context_tokens import count_context_tokens

    def fail_token_counter(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("backend.services.agent.context_tokens.litellm.token_counter", fail_token_counter)

    assert count_context_tokens(model_name="gpt-test", messages=[{"role": "user", "content": "hello"}]) is None
