# CALLING SPEC:
# - Purpose: implement focused service logic for `execution`.
# - Inputs: callers that import `backend/services/agent/tool_runtime_support/execution.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `execution`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

import logging
from typing import Any

from pydantic import ValidationError
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential

from backend.services.agent.tool_results import error_result
from backend.services.agent.tool_runtime_support.catalog import TOOLS
from backend.services.agent.tool_types import ToolContext, ToolExecutionResult
from backend.services.crud_policy import PolicyViolation
from backend.services.runtime_settings import resolve_runtime_settings

logger = logging.getLogger(__name__)


def execute_tool(name: str, arguments: dict[str, Any], context: ToolContext) -> ToolExecutionResult:
    definition = TOOLS.get(name)
    if definition is None:
        return error_result(f"unknown tool '{name}'")

    try:
        parsed = definition.args_model.model_validate(arguments)
    except ValidationError as exc:
        return error_result("invalid tool arguments", details=exc.errors())

    settings = resolve_runtime_settings(context.db)
    retrying = Retrying(
        stop=stop_after_attempt(settings.agent_retry_max_attempts),
        wait=wait_exponential(
            multiplier=settings.agent_retry_initial_wait_seconds,
            max=settings.agent_retry_max_wait_seconds,
            exp_base=settings.agent_retry_backoff_multiplier,
        ),
        retry=retry_if_exception(lambda exc: not isinstance(exc, (PolicyViolation, ValueError))),
        reraise=True,
    )

    try:
        result = None
        for attempt in retrying:
            with attempt:
                result = definition.handler(context, parsed)
        if result is None:  # pragma: no cover - defensive guard
            return error_result("tool execution failed", details="no result returned")
        return result
    except PolicyViolation as exc:
        return error_result("tool execution failed", details=exc.detail)
    except ValueError as exc:
        return error_result("tool execution failed", details=str(exc))
    except Exception as exc:  # pragma: no cover - guarded for runtime resilience
        logger.exception(
            "tool execution failed unexpectedly",
            extra={"tool_name": name, "error_type": type(exc).__name__},
        )
        return error_result("tool execution failed", details=str(exc))
