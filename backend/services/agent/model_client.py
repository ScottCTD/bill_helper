# CALLING SPEC:
# - Purpose: implement focused service logic for `model_client`.
# - Inputs: callers that import `backend/services/agent/model_client.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `model_client`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
import litellm
from backend.services.agent.model_client_support.client import (
    AgentModelError,
    LiteLLMModelClient,
)
from backend.services.agent.model_client_support.environment import (
    validate_litellm_environment,
)

__all__ = [
    "AgentModelError",
    "LiteLLMModelClient",
    "litellm",
    "validate_litellm_environment",
]
