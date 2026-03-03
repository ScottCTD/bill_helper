"""Pydantic schemas for benchmark case input and ground truth."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseInput(BaseModel):
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

class GroundTruthTag(BaseModel):
    name: str
    type: str | None = None

class GroundTruthEntity(BaseModel):
    name: str
    category: str | None = None

class GroundTruthEntry(BaseModel):
    kind: str = Field(pattern="^(EXPENSE|INCOME|TRANSFER)$")
    date: str = Field(description="ISO date YYYY-MM-DD")
    name: str
    amount_minor: int = Field(gt=0)
    currency_code: str | None = None
    from_entity: str
    to_entity: str
    tags: list[str] = Field(default_factory=list)


class GroundTruth(BaseModel):
    tags: list[GroundTruthTag] = Field(default_factory=list)
    entities: list[GroundTruthEntity] = Field(default_factory=list)
    entries: list[GroundTruthEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Predicted (extracted from agent tool calls)
# ---------------------------------------------------------------------------

class PredictedTag(BaseModel):
    name: str | None = None
    type: str | None = None

class PredictedEntity(BaseModel):
    name: str | None = None
    category: str | None = None

class PredictedEntry(BaseModel):
    kind: str | None = None
    date: str | None = None
    name: str | None = None
    amount_minor: int | None = None
    currency_code: str | None = None
    from_entity: str | None = None
    to_entity: str | None = None
    tags: list[str] = Field(default_factory=list)
    markdown_notes: str | None = None


class CaseResult(BaseModel):
    case_id: str
    model: str
    tags: list[PredictedTag] = Field(default_factory=list)
    entities: list[PredictedEntity] = Field(default_factory=list)
    entries: list[PredictedEntry] = Field(default_factory=list)
    run_status: str | None = None
    error: str | None = None
