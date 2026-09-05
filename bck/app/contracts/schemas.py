"""Shared Pydantic contracts — every module imports these instead of defining its own shapes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Modality(StrEnum):
    """Sensor modality for one input image. Cross-modal (optical+SAR) is the PS's own framing."""

    OPTICAL = "optical"
    SAR = "sar"


class ImageInput(BaseModel):
    """One uploaded image as it flows through the pipeline.

    `format` is left as a free string rather than an enum: which formats are accepted is
    ingestion's compatibility-check concern (F1-F3), not a rule contracts should pin.
    Modality-specific facts that aren't universal (GSD, CRS, bounds, acquisition timestamp,
    SAR polarization, etc.) belong in `metadata` rather than as top-level fields, since the
    set of relevant keys differs by modality and ticket didn't enumerate them.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    modality: Modality
    format: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class QueryRequest(BaseModel):
    """Parsed request the pipeline operates on: the user's query text plus its input images."""

    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1)
    images: list[ImageInput] = Field(default_factory=list)


class EvidenceType(StrEnum):
    """Evidence payload kinds, per Technical Implementation §2.7."""

    TEXT = "text"
    BBOX = "bbox"
    MASK = "mask"
    STATS = "stats"
    LAYER = "layer"


class Evidence(BaseModel):
    """Uniform schema every tool returns, per ARCHITECTURE.md's data-flow section:
    {id, tool, type, payload, confidence, timing}.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    tool: str
    type: EvidenceType
    payload: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    timing: float = Field(ge=0.0, description="Wall-clock seconds the tool took to produce this.")


class TraceStep(BaseModel):
    """One recorded hop through the pipeline, for the auditable execution trace."""

    model_config = ConfigDict(frozen=True)

    module: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    started_at: datetime
    completed_at: datetime | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class ExecutionTrace(BaseModel):
    """Ordered, auditable record of every module the pipeline invoked for one request."""

    model_config = ConfigDict(frozen=True)

    trace_id: str
    steps: list[TraceStep] = Field(default_factory=list)
    created_at: datetime


class Answer(BaseModel):
    """Final response shape returned to the API layer.

    verification/ forces an explicit abstention where evidence is insufficient
    (ARCHITECTURE.md) — `abstained` makes that a typed contract rather than something callers
    infer from an empty evidence list.
    """

    model_config = ConfigDict(frozen=True)

    text: str
    evidence: list[Evidence] = Field(default_factory=list)
    trace: ExecutionTrace
    confidence: float = Field(ge=0.0, le=1.0)
    abstained: bool = False
    abstention_reason: str | None = None

    @model_validator(mode="after")
    def _abstention_reason_matches_flag(self) -> Answer:
        if self.abstained and not self.abstention_reason:
            raise ValueError("abstention_reason is required when abstained is True")
        if not self.abstained and self.abstention_reason is not None:
            raise ValueError("abstention_reason must be null when abstained is False")
        return self
