# CALLING SPEC:
# - Purpose: provide benchmark support for `schemas`.
# - Inputs: callers that import `benchmark/schemas.py` and pass module-defined arguments or framework events.
# - Outputs: benchmark helpers, contracts, or entrypoints for `schemas`.
# - Side effects: benchmark data loading, execution, or reporting as implemented below.
"""Pydantic schemas for benchmark case input and ground truth."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseInput(BenchmarkModel):
    text: str = Field(description="User message text sent to the agent")
    attachment_paths: list[str] = Field(
        default_factory=list,
        description="Relative paths to attachment files (PDFs, images) within the case directory",
    )
    snapshot: str = Field(
        default="default",
        description="Name of the DB snapshot to use (under benchmark/fixtures/snapshots/)",
    )


# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

class GroundTruthTag(BenchmarkModel):
    name: str
    type: str | None = None

class GroundTruthEntity(BenchmarkModel):
    name: str
    category: str | None = None

class GroundTruthEntry(BenchmarkModel):
    kind: str = Field(pattern="^(EXPENSE|INCOME|TRANSFER)$")
    date: str = Field(description="ISO date YYYY-MM-DD")
    name: str
    amount_minor: int = Field(gt=0)
    currency_code: str | None = None
    from_entity: str
    to_entity: str
    tags: list[str] = Field(default_factory=list)


class GroundTruth(BenchmarkModel):
    tags: list[GroundTruthTag] = Field(default_factory=list)
    entities: list[GroundTruthEntity] = Field(default_factory=list)
    entries: list[GroundTruthEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Predicted (extracted from agent tool calls)
# ---------------------------------------------------------------------------

class PredictedTag(BenchmarkModel):
    name: str | None = None
    type: str | None = None

class PredictedEntity(BenchmarkModel):
    name: str | None = None
    category: str | None = None

class PredictedEntry(BenchmarkModel):
    kind: str | None = None
    date: str | None = None
    name: str | None = None
    amount_minor: int | None = None
    currency_code: str | None = None
    from_entity: str | None = None
    to_entity: str | None = None
    tags: list[str] = Field(default_factory=list)
    markdown_notes: str | None = None


class CaseResult(BenchmarkModel):
    case_id: str
    model: str
    tags: list[PredictedTag] = Field(default_factory=list)
    entities: list[PredictedEntity] = Field(default_factory=list)
    entries: list[PredictedEntry] = Field(default_factory=list)
    run_status: str | None = None
    error: str | None = None
