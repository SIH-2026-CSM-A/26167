"""Router schemas and data contracts for intent classification and tool dispatch."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TaskType(StrEnum):
    """Fixed task registry matching PS-specified operational capabilities."""

    VQA = "vqa"
    """Single-image Visual Question Answering over Optical or SAR imagery."""

    GROUNDING = "grounding"
    """Single-image referring expression segmentation or bounding-box localization."""

    CHANGE_VQA = "change_vqa"
    """Bi-temporal change detection, change description, and change-VQA
    across pre- and post-event scenes.
    """

    FUSION = "fusion"
    """Cross-modal joint analysis and rule-based reconciliation across
    co-registered Optical + SAR pairs.
    """

    ARCHIVE_SEARCH_BONUS = "archive_search_bonus"
    """Catalog semantic search and historical archive retrieval (PRD §11 bonus capability)."""


class IntentClassification(BaseModel):
    """Narrow, schema-constrained candidate intent.

    TaskType is the sole source of truth; no redundant boolean flags
    (e.g., requires_grounding, requires_cross_modal) are permitted.
    """

    model_config = ConfigDict(frozen=True)

    task_type: TaskType


class InputInventory(BaseModel):
    """Deterministic structural summary of the QueryRequest image payload."""

    model_config = ConfigDict(frozen=True)

    total_images: int
    has_optical: bool
    has_sar: bool
    optical_ids: list[str] = Field(default_factory=list)
    sar_ids: list[str] = Field(default_factory=list)


class VetoReasonCode(StrEnum):
    """Deterministic veto codes consumed by pipeline and verification layers."""

    EMPTY_QUERY = "EMPTY_QUERY"
    INSUFFICIENT_IMAGES = "INSUFFICIENT_IMAGES"
    EXCESS_IMAGES = "EXCESS_IMAGES"
    CROSS_MODAL_PAIR_MISSING = "CROSS_MODAL_PAIR_MISSING"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"


class VetoDecision(BaseModel):
    """Deterministic veto payload explaining why an intent cannot be executed."""

    model_config = ConfigDict(frozen=True)

    reason_code: VetoReasonCode
    message: str
    suggested_action: str


class DispatchPlan(BaseModel):
    """Parameter binding emitted for pipeline tool execution. Router does not run tools."""

    model_config = ConfigDict(frozen=True)

    tool_name: str
    image_bindings: dict[str, str]
    task_parameters: dict[str, Any] = Field(default_factory=dict)


class RouterDecision(BaseModel):
    """Final output emitted by app.router to app.pipeline."""

    model_config = ConfigDict(frozen=True)

    status: Literal["dispatched", "vetoed"]
    intent: IntentClassification
    dispatch_plan: DispatchPlan | None = None
    veto: VetoDecision | None = None

    @property
    def is_dispatched(self) -> bool:
        return self.status == "dispatched"

    @property
    def is_vetoed(self) -> bool:
        return self.status == "vetoed"
