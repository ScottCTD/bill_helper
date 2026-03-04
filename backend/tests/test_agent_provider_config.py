from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.services.agent.model_client import LiteLLMModelClient
from backend.services.agent.runtime import ensure_agent_available


def test_model_client_passes_custom_base_url_and_api_key_to_litellm():
    fake_completion = MagicMock()
    fake_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="test", tool_calls=None))],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )

    with patch(
        "backend.services.agent.model_client.litellm.completion", fake_completion
    ):
        client = LiteLLMModelClient(
            model_name="openai/gpt-4",
            tools=[],
            retry_max_attempts=1,
            retry_initial_wait_seconds=0.1,
            retry_max_wait_seconds=1.0,
            retry_backoff_multiplier=2.0,
            base_url="https://custom-api.example.com/v1",
            api_key="sk-custom-test-key-12345",
        )
        client.complete([{"role": "user", "content": "test"}])

    assert fake_completion.call_count == 1
    call_kwargs = fake_completion.call_args[1]
    assert call_kwargs["base_url"] == "https://custom-api.example.com/v1"
    assert call_kwargs["api_key"] == "sk-custom-test-key-12345"


def test_model_client_without_custom_config_uses_litellm_defaults():
    fake_completion = MagicMock()
    fake_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="test", tool_calls=None))],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )

    with patch(
        "backend.services.agent.model_client.litellm.completion", fake_completion
    ):
        client = LiteLLMModelClient(
            model_name="openai/gpt-4",
            tools=[],
            retry_max_attempts=1,
            retry_initial_wait_seconds=0.1,
            retry_max_wait_seconds=1.0,
            retry_backoff_multiplier=2.0,
        )
        client.complete([{"role": "user", "content": "test"}])

    assert fake_completion.call_count == 1
    call_kwargs = fake_completion.call_args[1]
    assert "base_url" not in call_kwargs
    assert "api_key" not in call_kwargs


def test_model_client_strips_trailing_slash_from_base_url():
    fake_completion = MagicMock()
    fake_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="test", tool_calls=None))],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )

    with patch(
        "backend.services.agent.model_client.litellm.completion", fake_completion
    ):
        client = LiteLLMModelClient(
            model_name="openai/gpt-4",
            tools=[],
            retry_max_attempts=1,
            retry_initial_wait_seconds=0.1,
            retry_max_wait_seconds=1.0,
            retry_backoff_multiplier=2.0,
            base_url="https://custom-api.example.com/v1/",
            api_key="sk-test-key",
        )
        client.complete([{"role": "user", "content": "test"}])

    call_kwargs = fake_completion.call_args[1]
    assert call_kwargs["base_url"] == "https://custom-api.example.com/v1"


def test_model_client_normalizes_empty_strings_to_none():
    fake_completion = MagicMock()
    fake_completion.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="test", tool_calls=None))],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )

    with patch(
        "backend.services.agent.model_client.litellm.completion", fake_completion
    ):
        client = LiteLLMModelClient(
            model_name="openai/gpt-4",
            tools=[],
            retry_max_attempts=1,
            retry_initial_wait_seconds=0.1,
            retry_max_wait_seconds=1.0,
            retry_backoff_multiplier=2.0,
            base_url="   ",
            api_key="  ",
        )
        client.complete([{"role": "user", "content": "test"}])

    call_kwargs = fake_completion.call_args[1]
    assert "base_url" not in call_kwargs
    assert "api_key" not in call_kwargs


def test_ensure_agent_available_skips_validation_with_custom_credentials():
    """When custom base_url or api_key is configured, validation should pass even without env vars."""
    mock_session = MagicMock()

    with patch(
        "backend.services.agent.runtime.resolve_runtime_settings"
    ) as mock_resolve:
        # Test with both set
        mock_resolve.return_value = MagicMock(
            agent_model="openai/gpt-4",
            agent_base_url="https://custom-api.example.com/v1",
            agent_api_key="sk-custom-key",
        )
        # Should not raise any exception
        ensure_agent_available(mock_session)

        # Test with only base_url set
        mock_resolve.return_value = MagicMock(
            agent_model="openai/gpt-4",
            agent_base_url="https://custom-api.example.com/v1",
            agent_api_key=None,
        )
        ensure_agent_available(mock_session)

        # Test with only api_key set
        mock_resolve.return_value = MagicMock(
            agent_model="openai/gpt-4",
            agent_base_url=None,
            agent_api_key="sk-custom-key",
        )
        ensure_agent_available(mock_session)


def test_ensure_agent_available_validates_env_when_no_custom_config():
    """When no custom config is set, should validate env vars and raise if missing."""
    mock_session = MagicMock()

    with (
        patch(
            "backend.services.agent.runtime.resolve_runtime_settings"
        ) as mock_resolve,
        patch(
            "backend.services.agent.runtime.validate_litellm_environment"
        ) as mock_validate,
    ):
        mock_resolve.return_value = MagicMock(
            agent_model="openai/gpt-4",
            agent_base_url=None,
            agent_api_key=None,
        )
        mock_validate.return_value = (False, ["OPENAI_API_KEY"], "openai/gpt-4")

        from backend.services.agent.runtime import AgentRuntimeUnavailable

        try:
            ensure_agent_available(mock_session)
            assert False, "Should have raised AgentRuntimeUnavailable"
        except AgentRuntimeUnavailable as e:
            assert "OPENAI_API_KEY" in str(e)
            assert "custom base_url and api_key" in str(e)
