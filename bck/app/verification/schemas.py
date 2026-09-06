"""Pydantic schemas and enums for the verification layer (SHIVA-004, F15/F16)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts import Evidence


class VerificationStatus(StrEnum):
    """High-level outcome of verification."""

    VERIFIED = "verified"
    ABSTAINED = "abstained"


class DisagreementCategory(StrEnum):
    """Classification of detected cross-modal conflicts or ungrounded claims."""

    CROSS_MODAL_CONFLICT = "cross_modal_conflict"
    UNSUPPORTED_NUMERIC_CLAIM = "unsupported_numeric_claim"
    SENSOR_PHYSICAL_LIMITATION = "sensor_physical_limitation"
    COMPLEMENTARY_OBSERVATION = "complementary_observation"
    NOT_COMPARABLE = "not_comparable"


class CrossModalRelationship(StrEnum):
    """Five-state relationship model between multi-sensor observations."""

    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    COMPLEMENTARY = "complementary"
    NOT_COMPARABLE = "not_comparable"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AbstentionReasonCode(StrEnum):
    """Deterministic typed abstention reason codes."""

    NO_EVIDENCE_PRODUCED = "NO_EVIDENCE_PRODUCED"
    INSUFFICIENT_CONFIDENCE = "INSUFFICIENT_CONFIDENCE"
    SENSOR_PHYSICAL_LIMITATION = "SENSOR_PHYSICAL_LIMITATION"
    SEVERE_MODALITY_CONFLICT = "SEVERE_MODALITY_CONFLICT"
    UNVERIFIABLE_MANDATORY_CLAIM = "UNVERIFIABLE_MANDATORY_CLAIM"


class DisagreementRecord(BaseModel):
    """Auditable record of a detected discrepancy, caveat, or downgraded claim."""

    model_config = ConfigDict(frozen=True)

    rule_id: str
    category: DisagreementCategory
    description: str
    action_taken: str  # "downgraded" | "reconciled" | "caveated" | "abstained"
    conflicting_evidence_ids: list[str] = Field(default_factory=list)


class VerificationPolicy(BaseModel):
    """Configurable thresholds and penalties for verification.

    Defaults represent empirical implementation baselines per Features Spec F15/F22.
    """

    model_config = ConfigDict(frozen=True)

    min_confidence_floor: float = 0.30
    unsupported_numeric_penalty: float = 0.15
    severe_conflict_penalty: float = 0.40
    max_total_penalty: float = 0.50


class VerificationDecision(BaseModel):
    """Immutable result emitted by app.verification."""

    model_config = ConfigDict(frozen=True)

    status: Literal["verified", "abstained"]
    abstained: bool
    abstention_reason: str | None = None
    verified_evidence: list[Evidence] = Field(default_factory=list)
    disagreements: list[DisagreementRecord] = Field(default_factory=list)
    confidence_penalty: float = Field(default=0.0, ge=0.0, le=1.0)
    filtered_evidence_ids: list[str] = Field(default_factory=list)

    @property
    def is_abstained(self) -> bool:
        return self.abstained

    @property
    def is_verified(self) -> bool:
        return not self.abstained

    @property
    def effective_confidence(self) -> float:
        """Mean confidence of verified evidence minus penalty, clamped to [0.0, 1.0]."""
        if self.abstained or not self.verified_evidence:
            return 0.0
        mean_conf = sum(e.confidence for e in self.verified_evidence) / len(self.verified_evidence)
        return max(0.0, min(1.0, mean_conf - self.confidence_penalty))

    def as_pipeline_tuple(self) -> tuple[list[Evidence], bool, str | None]:
        """Direct backward-compatibility unpack for pipeline seam in app.pipeline.stages."""
        return self.verified_evidence, self.abstained, self.abstention_reason
