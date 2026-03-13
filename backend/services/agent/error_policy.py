# CALLING SPEC:
# - Purpose: implement focused service logic for `error_policy`.
# - Inputs: callers that import `backend/services/agent/error_policy.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `error_policy`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Generic, TypeVar


logger = logging.getLogger(__name__)

TValue = TypeVar("TValue")


@dataclass(frozen=True)
class RecoverableError:
    scope: str
    error_type: str
    message: str
    context: dict[str, Any]


@dataclass(frozen=True)
class RecoverableResult(Generic[TValue]):
    value: TValue
    error: RecoverableError | None = None


def recoverable_result(
    *,
    scope: str,
    fallback: TValue,
    error: Exception,
    context: dict[str, Any] | None = None,
    log: logging.Logger | None = None,
) -> RecoverableResult[TValue]:
    metadata = context or {}
    logger_to_use = log or logger
    logger_to_use.debug(
        "recoverable error in %s (%s): %s | context=%s",
        scope,
        type(error).__name__,
        str(error),
        metadata,
    )
    return RecoverableResult(
        value=fallback,
        error=RecoverableError(
            scope=scope,
            error_type=type(error).__name__,
            message=str(error),
            context=metadata,
        ),
    )
