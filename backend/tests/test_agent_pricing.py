from __future__ import annotations


def test_calculate_usage_costs_uses_configured_model_name(monkeypatch):
    from backend.services.agent import pricing

    attempted_models: list[str] = []
    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(*, model: str, prompt_tokens: int, completion_tokens: int):
        attempted_models.append(model)
        if model == "openai/gpt-5-nano":
            assert prompt_tokens == 2000
            assert completion_tokens == 500
            return (0.0015, 0.0025)
        raise ValueError("model not found")

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="openai/gpt-5-nano",
        input_tokens=2000,
        output_tokens=500,
    )

    assert attempted_models[0] == "openai/gpt-5-nano"
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

    monkeypatch.setattr(pricing, "_refresh_model_cost_map_if_due", lambda: None)

    def fake_cost_per_token(*, model: str, prompt_tokens: int, completion_tokens: int):
        assert model == "openai/gpt-5-nano"
        assert prompt_tokens == 300
        assert completion_tokens == 0
        return (0.00021, 0.0)

    monkeypatch.setattr(pricing, "_cost_per_token", fake_cost_per_token)

    costs = pricing.calculate_usage_costs(
        model_name="openai/gpt-5-nano",
        input_tokens=300,
        output_tokens=None,
    )

    assert costs.input_cost_usd == 0.00021
    assert costs.output_cost_usd is None
    assert costs.total_cost_usd == 0.00021
