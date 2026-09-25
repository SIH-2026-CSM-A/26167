"""Router schemas and data contracts for intent classification and tool dispatch."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    CHANGE_DESCRIBE = "change_describe"
    """Bi-temporal change detection followed by VQA on the largest changed region: the one
    fixed two-tool sequence the router supports (change_detection -> vqa_grounding).
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
    unknown_ids: list[str] = Field(default_factory=list)


class VetoReasonCode(StrEnum):
    """Deterministic veto codes consumed by pipeline and verification layers."""

    EMPTY_QUERY = "EMPTY_QUERY"
    INSUFFICIENT_IMAGES = "INSUFFICIENT_IMAGES"
    EXCESS_IMAGES = "EXCESS_IMAGES"
    CROSS_MODAL_PAIR_MISSING = "CROSS_MODAL_PAIR_MISSING"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    MODALITY_UNKNOWN = "MODALITY_UNKNOWN"
    TEMPORAL_ORDER_MISSING = "TEMPORAL_ORDER_MISSING"
    EO_CRS_MISMATCH = "EO_CRS_MISMATCH"
    EO_INSUFFICIENT_OVERLAP = "EO_INSUFFICIENT_OVERLAP"
    EO_GSD_MISMATCH = "EO_GSD_MISMATCH"
    EO_ACQUISITION_ORDER_REVERSED = "EO_ACQUISITION_ORDER_REVERSED"


class VetoDecision(BaseModel):
    """Deterministic veto payload explaining why an intent cannot be executed."""

    model_config = ConfigDict(frozen=True)

    reason_code: VetoReasonCode
    message: str
    suggested_action: str


# Hard cap on specialist tool executions for one query, first tool included. The only
# sequence the router plans is two tools long; the pipeline also counts executions.
MAX_TOOL_CALLS = 2


class ToolStep(BaseModel):
    """A tool that runs after the plan's first tool, fed by the previous step's output."""

    model_config = ConfigDict(frozen=True)

    tool_name: str
    image_bindings: dict[str, str]
    task_parameters: dict[str, Any] = Field(default_factory=dict)
    input_from_previous: Literal["largest_change_component"]
    """What the previous step hands over. Only one handoff exists: the post image cropped to
    the largest connected component of the change mask."""


class DispatchPlan(BaseModel):
    """Parameter binding emitted for pipeline tool execution. Router does not run tools.

    `tool_name` / `image_bindings` / `task_parameters` describe the first (for most plans,
    the only) tool. `followups` is empty except for CHANGE_DESCRIBE.
    """

    model_config = ConfigDict(frozen=True)

    tool_name: str
    image_bindings: dict[str, str]
    task_parameters: dict[str, Any] = Field(default_factory=dict)
    followups: tuple[ToolStep, ...] = ()

    @model_validator(mode="after")
    def _within_tool_call_cap(self) -> DispatchPlan:
        if 1 + len(self.followups) > MAX_TOOL_CALLS:
            raise ValueError(
                f"plan has {1 + len(self.followups)} tool calls; MAX_TOOL_CALLS={MAX_TOOL_CALLS}"
            )
        return self

    @property
    def tool_sequence(self) -> list[str]:
        return [self.tool_name, *(step.tool_name for step in self.followups)]


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
