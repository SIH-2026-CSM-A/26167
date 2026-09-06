"""Central verification evaluator and trace integration (SHIVA-004, F15/F16)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.contracts import Evidence, ImageInput, TraceStep
from app.verification.rules import (
    evaluate_cloud_sar_reconciliation,
    evaluate_confidence_floor,
    evaluate_cross_modal_conflict,
    evaluate_empty_evidence,
    evaluate_narrative_claim_grounding,
    evaluate_sensor_compatibility,
    evaluate_structured_numeric_grounding,
)
from app.verification.schemas import (
    DisagreementCategory,
    DisagreementRecord,
    VerificationDecision,
    VerificationPolicy,
    VerificationStatus,
)


def verify(
    evidence: list[Evidence],
    raw_query: str | None = None,
    images: list[ImageInput] | None = None,
    policy: VerificationPolicy | None = None,
    supporting_observations: list[str] | tuple[str, ...] | None = None,
) -> VerificationDecision:
    """Master deterministic verification entrypoint.

    Executes sequential verification stages:
    1. Empty Evidence Gate (RULE-VERIFY-01)
    2. Physical Sensor Compatibility Gate (RULE-VERIFY-03)
    3. Narrative Claim Grounding (RULE-VERIFY-09)
    4. Confidence Floor Gate (RULE-VERIFY-02)
    5. Irreconcilable Cross-Modal Conflict Check (RULE-VERIFY-CONFLICT)
    6. Structured Numeric Grounding (RULE-VERIFY-06)
    7. Cloud vs. SAR Radar Reconciliation (RULE-VERIFY-04)
    """
    active_policy = policy or VerificationPolicy()

    # Stage 1: Empty Evidence Gate
    is_empty, empty_reason = evaluate_empty_evidence(evidence)
    if is_empty:
        return VerificationDecision(
            status=VerificationStatus.ABSTAINED,
            abstained=True,
            abstention_reason=empty_reason,
            verified_evidence=[],
            disagreements=[],
            confidence_penalty=0.0,
            filtered_evidence_ids=[],
        )

    # Stage 2: Physical Sensor Compatibility Gate
    is_incompatible, sensor_reason = evaluate_sensor_compatibility(raw_query, images)
    if is_incompatible:
        return VerificationDecision(
            status=VerificationStatus.ABSTAINED,
            abstained=True,
            abstention_reason=sensor_reason,
            verified_evidence=[],
            disagreements=[
                DisagreementRecord(
                    rule_id="RULE-VERIFY-03",
                    category=DisagreementCategory.SENSOR_PHYSICAL_LIMITATION,
                    description=sensor_reason or "",
                    action_taken="abstained",
                    conflicting_evidence_ids=[e.id for e in evidence],
                )
            ],
            confidence_penalty=0.0,
            filtered_evidence_ids=[],
        )

    # Stage 3: Narrative Claim Grounding Gate (runs before the confidence floor so a
    # claim with a supported remainder can survive with real, non-fabricated confidence
    # instead of triggering full abstention alongside its unsupported siblings)
    claim_evidence, claim_records = evaluate_narrative_claim_grounding(
        evidence,
        list(supporting_observations or ()),
    )

    # Stage 4: Confidence Floor Gate
    surviving, filtered_ids, is_subfloor, floor_reason = evaluate_confidence_floor(
        claim_evidence,
        active_policy.min_confidence_floor,
    )
    if is_subfloor:
        return VerificationDecision(
            status=VerificationStatus.ABSTAINED,
            abstained=True,
            abstention_reason=floor_reason,
            verified_evidence=[],
            disagreements=claim_records,
            confidence_penalty=0.0,
            filtered_evidence_ids=filtered_ids,
        )

    # Stage 5: Irreconcilable Cross-Modal Conflict Check
    is_severe, severe_reason, severe_records, severe_penalty = evaluate_cross_modal_conflict(
        surviving,
        images,
        active_policy,
    )
    if is_severe:
        return VerificationDecision(
            status=VerificationStatus.ABSTAINED,
            abstained=True,
            abstention_reason=severe_reason,
            verified_evidence=[],
            disagreements=severe_records,
            confidence_penalty=severe_penalty,
            filtered_evidence_ids=filtered_ids,
        )

    # Stage 6: Structured Numeric Grounding Check
    numeric_records, numeric_penalty = evaluate_structured_numeric_grounding(
        surviving,
        active_policy,
    )

    # Stage 7: Cloud vs. SAR Radar Reconciliation Check
    reconciliation_records = evaluate_cloud_sar_reconciliation(surviving)

    all_disagreements = claim_records + numeric_records + reconciliation_records
    total_penalty = min(numeric_penalty, active_policy.max_total_penalty)

    return VerificationDecision(
        status=VerificationStatus.VERIFIED,
        abstained=False,
        abstention_reason=None,
        verified_evidence=surviving,
        disagreements=all_disagreements,
        confidence_penalty=total_penalty,
        filtered_evidence_ids=filtered_ids,
    )


def verification_trace_params(decision: VerificationDecision) -> dict[str, Any]:
    """Generate strictly JSON-serializable parameter dictionary for TraceStep.params."""
    status_str = (
        decision.status.value if hasattr(decision.status, "value") else str(decision.status)
    )
    return {
        "status": str(status_str),
        "abstained": bool(decision.abstained),
        "abstention_reason": decision.abstention_reason,
        "confidence_penalty": round(float(decision.confidence_penalty), 4),
        "effective_confidence": round(float(decision.effective_confidence), 4),
        "retained_evidence_count": len(decision.verified_evidence),
        "filtered_evidence_count": len(decision.filtered_evidence_ids),
        "filtered_evidence_ids": list(decision.filtered_evidence_ids),
        "disagreement_count": len(decision.disagreements),
        "rejected_claim_count": sum(
            1 for d in decision.disagreements if d.rule_id == "RULE-VERIFY-09"
        ),
        "disagreements": [
            {
                "rule_id": d.rule_id,
                "category": (
                    str(d.category.value) if hasattr(d.category, "value") else str(d.category)
                ),
                "description": d.description,
                "action_taken": d.action_taken,
                "conflicting_evidence_ids": list(d.conflicting_evidence_ids),
            }
            for d in decision.disagreements
        ],
    }


def create_verification_trace_step(
    decision: VerificationDecision,
    started_at: datetime,
    completed_at: datetime | None = None,
) -> TraceStep:
    """Build a valid TraceStep contract representing the verification hop."""
    return TraceStep(
        module="verification",
        action="verify" if decision.is_verified else "abstain",
        params=verification_trace_params(decision),
        confidence=decision.effective_confidence,
        started_at=started_at,
        completed_at=completed_at or datetime.now(UTC),
        evidence_ids=[e.id for e in decision.verified_evidence],
    )
