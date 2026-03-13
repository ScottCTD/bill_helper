# CALLING SPEC:
# - Purpose: implement focused service logic for `tool_types`.
# - Inputs: callers that import `backend/services/agent/tool_types.py` and pass module-defined arguments or framework events.
# - Outputs: service functions, contracts, or helpers exported by `tool_types`.
# - Side effects: module-defined persistence, validation, or orchestration behavior.
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session


class ToolExecutionStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


@dataclass(slots=True)
class ToolExecutionResult:
    output_text: str
    output_json: dict[str, Any]
    status: ToolExecutionStatus

    def __post_init__(self) -> None:
        self.status = ToolExecutionStatus(self.status)
        self.output_json = dict(self.output_json)
        self.output_json["status"] = self.status.value


@dataclass(slots=True)
class ToolContext:
    db: Session
    run_id: str
    principal_name: str | None = None
    principal_user_id: str | None = None
    principal_is_admin: bool | None = None
