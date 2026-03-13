# CALLING SPEC:
# - Purpose: implement focused service logic for `run_orchestrator`.
# - Inputs: callers that import `backend/services/agent/run_orchestrator.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `run_orchestrator`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any, Generic, TypeVar

from backend.services.agent.model_client import AgentModelError
from backend.services.agent.protocol_helpers import (
    USAGE_FIELDS,
    accumulate_usage_totals,
    extract_usage_dict,
)

logger = logging.getLogger(__name__)


class RunLoopOutcome(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass(slots=True)
class AssistantStepContext:
    step_index: int
    assistant_message: dict[str, Any]
    assistant_content: str
    model_reasoning: str
    tool_calls: list[dict[str, Any]]
    usage: dict[str, int | None]


PreparedToolCallT = TypeVar("PreparedToolCallT")
StreamPayload = dict[str, Any]
ModelStepGenerator = Generator[StreamPayload, None, dict[str, Any]]


class AgentRunLoopAdapter(ABC, Generic[PreparedToolCallT]):
    @property
    @abstractmethod
    def max_steps(self) -> int:
        raise NotImplementedError

    @abstractmethod
    def build_initial_messages(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def initial_usage_totals(self) -> dict[str, int | None]:
        raise NotImplementedError

    @abstractmethod
    def apply_usage_totals(self, usage_totals: dict[str, int | None]) -> None:
        raise NotImplementedError

    @abstractmethod
    def call_model_step(
        self,
        *,
        step_index: int,
        llm_messages: list[dict[str, Any]],
    ) -> ModelStepGenerator:
        raise NotImplementedError

    @abstractmethod
    def prepare_tool_calls(
        self,
        *,
        step: AssistantStepContext,
        llm_messages: list[dict[str, Any]],
    ) -> tuple[list[PreparedToolCallT], list[StreamPayload]]:
        raise NotImplementedError

    @abstractmethod
    def execute_prepared_tool_call(
        self,
        *,
        step: AssistantStepContext,
        prepared_tool_call: PreparedToolCallT,
        llm_messages: list[dict[str, Any]],
    ) -> list[StreamPayload]:
        raise NotImplementedError

    @abstractmethod
    def record_model_reasoning(self, *, step: AssistantStepContext) -> list[StreamPayload]:
        raise NotImplementedError

    @abstractmethod
    def complete(self, *, step: AssistantStepContext) -> list[StreamPayload]:
        raise NotImplementedError

    @abstractmethod
    def fail_max_steps(self) -> list[StreamPayload]:
        raise NotImplementedError

    @abstractmethod
    def fail_model_error(self, error: AgentModelError) -> list[StreamPayload]:
        raise NotImplementedError

    @abstractmethod
    def fail_unexpected_error(self, error: Exception) -> list[StreamPayload]:
        raise NotImplementedError

    def on_loop_started(self) -> list[StreamPayload]:
        return []

    def on_stopped(self) -> list[StreamPayload]:
        return []

    def after_tool_turn(
        self,
        *,
        step: AssistantStepContext,
        llm_messages: list[dict[str, Any]],
    ) -> list[StreamPayload]:
        return []

    def is_stopped(self) -> bool:
        return False


def run_agent_loop(
    adapter: AgentRunLoopAdapter[PreparedToolCallT],
) -> Generator[StreamPayload, None, RunLoopOutcome]:
    for payload in adapter.on_loop_started():
        yield payload

    llm_messages = adapter.build_initial_messages()
    usage_totals = adapter.initial_usage_totals()
    current_step_index = 0

    try:
        for step_index in range(adapter.max_steps):
            current_step_index = step_index + 1
            if adapter.is_stopped():
                for payload in adapter.on_stopped():
                    yield payload
                return RunLoopOutcome.STOPPED

            assistant_message = yield from adapter.call_model_step(
                step_index=step_index + 1,
                llm_messages=llm_messages,
            )
            if not isinstance(assistant_message, dict):
                raise AgentModelError("model request failed: invalid response payload")

            if adapter.is_stopped():
                for payload in adapter.on_stopped():
                    yield payload
                return RunLoopOutcome.STOPPED

            usage = extract_usage_dict(assistant_message, fields=USAGE_FIELDS)
            accumulate_usage_totals(usage_totals, usage, fields=USAGE_FIELDS)
            adapter.apply_usage_totals(usage_totals)

            tool_calls = assistant_message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                tool_calls = []

            step = AssistantStepContext(
                step_index=step_index + 1,
                assistant_message=assistant_message,
                assistant_content=str(assistant_message.get("content") or ""),
                model_reasoning=str(assistant_message.get("reasoning") or "").strip(),
                tool_calls=tool_calls,
                usage=usage,
            )

            if step.tool_calls:
                prepared_calls, payloads = adapter.prepare_tool_calls(
                    step=step,
                    llm_messages=llm_messages,
                )
                for payload in payloads:
                    yield payload

                for prepared_tool_call in prepared_calls:
                    if adapter.is_stopped():
                        for payload in adapter.on_stopped():
                            yield payload
                        return RunLoopOutcome.STOPPED
                    for payload in adapter.execute_prepared_tool_call(
                        step=step,
                        prepared_tool_call=prepared_tool_call,
                        llm_messages=llm_messages,
                    ):
                        yield payload

                for payload in adapter.after_tool_turn(
                    step=step,
                    llm_messages=llm_messages,
                ):
                    yield payload
                continue

            for payload in adapter.record_model_reasoning(step=step):
                yield payload
            for payload in adapter.complete(step=step):
                yield payload
            return RunLoopOutcome.COMPLETED

        for payload in adapter.fail_max_steps():
            yield payload
        return RunLoopOutcome.FAILED
    except AgentModelError as error:
        for payload in adapter.fail_model_error(error):
            yield payload
        return RunLoopOutcome.FAILED
    except Exception as error:  # pragma: no cover - defensive guard
        logger.exception(
            "agent run loop failed unexpectedly",
            extra={
                "adapter_type": type(adapter).__name__,
                "step_index": current_step_index,
            },
        )
        for payload in adapter.fail_unexpected_error(error):
            yield payload
        return RunLoopOutcome.FAILED
