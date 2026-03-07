from __future__ import annotations


def test_calculate_usage_costs_uses_configured_model_name(monkeypatch):
    from backend.services.agent import pricing

    attempted_calls: list[dict[str, object]] = []
    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(**kwargs):
        attempted_calls.append(kwargs)
        if kwargs["model"] == "openai/gpt-5-nano":
            return (0.0015, 0.0025)
        raise ValueError("model not found")

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="openai/gpt-5-nano",
        input_tokens=2000,
        output_tokens=500,
        cache_read_tokens=None,
        cache_write_tokens=None,
    )

    assert attempted_calls == [
        {
            "model": "openai/gpt-5-nano",
            "prompt_tokens": 2000,
            "completion_tokens": 500,
        }
    ]
    assert costs.input_cost_usd == 0.0015
    assert costs.output_cost_usd == 0.0025
    assert costs.total_cost_usd == 0.004


def test_calculate_usage_costs_with_no_usage_returns_null_costs(monkeypatch):
    from backend.services.agent import pricing

    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fail_cost_per_token(*, model: str, prompt_tokens: int, completion_tokens: int):
        raise AssertionError("cost calculation should not be called without usage tokens")

    monkeypatch.setattr(pricing, "_cost_per_token", fail_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="openai/gpt-5-nano",
        input_tokens=None,
        output_tokens=None,
    )

    assert costs.input_cost_usd is None
    assert costs.output_cost_usd is None
    assert costs.total_cost_usd is None


def test_calculate_usage_costs_with_partial_usage_uses_available_side(monkeypatch):
    from backend.services.agent import pricing

    attempted_calls: list[dict[str, object]] = []
    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(**kwargs):
        attempted_calls.append(kwargs)
        return (0.00021, 0.0)

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="openai/gpt-5-nano",
        input_tokens=300,
        output_tokens=None,
        cache_read_tokens=None,
        cache_write_tokens=None,
    )

    assert attempted_calls == [
        {
            "model": "openai/gpt-5-nano",
            "prompt_tokens": 300,
            "completion_tokens": 0,
        }
    ]
    assert costs.input_cost_usd == 0.00021
    assert costs.output_cost_usd is None
    assert costs.total_cost_usd == 0.00021


def test_calculate_usage_costs_applies_cache_read_discount(monkeypatch):
    from backend.services.agent import pricing

    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(**kwargs):
        assert kwargs == {
            "model": "us.anthropic.claude-sonnet-4-6",
            "prompt_tokens": 100,
            "completion_tokens": 15,
            "cache_read_input_tokens": 80,
            "cache_creation_input_tokens": 0,
        }
        return (0.000096, 0.0002475)

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="us.anthropic.claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=15,
        cache_read_tokens=80,
        cache_write_tokens=0,
    )

    assert costs.input_cost_usd == 0.000096
    assert costs.output_cost_usd == 0.0002475
    assert costs.total_cost_usd == 0.0003435


def test_calculate_usage_costs_applies_cache_write_premium(monkeypatch):
    from backend.services.agent import pricing

    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(**kwargs):
        assert kwargs == {
            "model": "us.anthropic.claude-sonnet-4-6",
            "prompt_tokens": 40,
            "completion_tokens": 15,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 20,
        }
        return (0.0001155, 0.0002475)

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="us.anthropic.claude-sonnet-4-6",
        input_tokens=40,
        output_tokens=15,
        cache_read_tokens=0,
        cache_write_tokens=20,
    )

    assert costs.input_cost_usd == 0.0001155
    assert costs.output_cost_usd == 0.0002475
    assert costs.total_cost_usd == 0.000363


def test_calculate_usage_costs_handles_mixed_cached_and_uncached_prompt_totals(monkeypatch):
    from backend.services.agent import pricing

    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(**kwargs):
        assert kwargs == {
            "model": "us.anthropic.claude-sonnet-4-6",
            "prompt_tokens": 120,
            "completion_tokens": 15,
            "cache_read_input_tokens": 80,
            "cache_creation_input_tokens": 20,
        }
        return (0.0001749, 0.0002475)

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="us.anthropic.claude-sonnet-4-6",
        input_tokens=120,
        output_tokens=15,
        cache_read_tokens=80,
        cache_write_tokens=20,
    )

    assert costs.input_cost_usd == 0.0001749
    assert costs.output_cost_usd == 0.0002475
    assert costs.total_cost_usd == 0.0004224
