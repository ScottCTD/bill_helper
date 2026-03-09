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


@dataclass(slots=True)
class ToolContext:
    db: Session
    run_id: str
