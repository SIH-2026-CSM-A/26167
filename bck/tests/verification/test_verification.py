"""Unit tests for app.verification module (SHIVA-004, F15/F16)."""

import uuid
from datetime import UTC, datetime

from app.contracts import Evidence, EvidenceType, ImageInput, Modality
from app.verification import (
    AbstentionReasonCode,
    CrossModalRelationship,
    DisagreementCategory,
    DisagreementRecord,
    VerificationDecision,
    VerificationPolicy,
    VerificationStatus,
    create_verification_trace_step,
    verification_trace_params,
    verify,
)
from app.verification.rules import (
    evaluate_cloud_sar_reconciliation,
    evaluate_confidence_floor,
    evaluate_cross_modal_conflict,
    evaluate_empty_evidence,
    evaluate_sensor_compatibility,
    evaluate_structured_numeric_grounding,
)


def _evidence(
    tool: str = "test_tool",
    ev_type: EvidenceType = EvidenceType.TEXT,
    payload: dict | None = None,
    confidence: float = 0.8,
    ev_id: str | None = None,
    timing: float = 0.05,
) -> Evidence:
    return Evidence(
        id=ev_id or str(uuid.uuid4()),
        tool=tool,
        type=ev_type,
        payload=payload or {},
        confidence=confidence,
        timing=timing,
    )


# ---------------------------------------------------------------------------
# 1. Schemas, Enums, and Decision Properties
# ---------------------------------------------------------------------------
def test_verification_status_enums():
    assert VerificationStatus.VERIFIED == "verified"
    assert VerificationStatus.ABSTAINED == "abstained"


def test_disagreement_category_enums():
    assert DisagreementCategory.CROSS_MODAL_CONFLICT == "cross_modal_conflict"
    assert DisagreementCategory.UNSUPPORTED_NUMERIC_CLAIM == "unsupported_numeric_claim"
    assert DisagreementCategory.SENSOR_PHYSICAL_LIMITATION == "sensor_physical_limitation"
    assert DisagreementCategory.COMPLEMENTARY_OBSERVATION == "complementary_observation"
    assert DisagreementCategory.NOT_COMPARABLE == "not_comparable"


def test_cross_modal_relationship_enums():
    assert CrossModalRelationship.AGREEMENT == "agreement"
    assert CrossModalRelationship.DISAGREEMENT == "disagreement"
    assert CrossModalRelationship.COMPLEMENTARY == "complementary"
    assert CrossModalRelationship.NOT_COMPARABLE == "not_comparable"
    assert CrossModalRelationship.INSUFFICIENT_EVIDENCE == "insufficient_evidence"


def test_abstention_reason_codes():
    assert AbstentionReasonCode.NO_EVIDENCE_PRODUCED == "NO_EVIDENCE_PRODUCED"
    assert AbstentionReasonCode.INSUFFICIENT_CONFIDENCE == "INSUFFICIENT_CONFIDENCE"
    assert AbstentionReasonCode.SENSOR_PHYSICAL_LIMITATION == "SENSOR_PHYSICAL_LIMITATION"
    assert AbstentionReasonCode.SEVERE_MODALITY_CONFLICT == "SEVERE_MODALITY_CONFLICT"
    assert AbstentionReasonCode.UNVERIFIABLE_MANDATORY_CLAIM == "UNVERIFIABLE_MANDATORY_CLAIM"


def test_verification_policy_defaults():
    policy = VerificationPolicy()
    assert policy.min_confidence_floor == 0.30
    assert policy.unsupported_numeric_penalty == 0.15
    assert policy.severe_conflict_penalty == 0.40
    assert policy.max_total_penalty == 0.50


def test_verification_decision_effective_confidence_and_properties():
    e1 = _evidence(confidence=0.8)
    e2 = _evidence(confidence=0.6)

    # Normal verified case with penalty
    decision = VerificationDecision(
        status=VerificationStatus.VERIFIED,
        abstained=False,
        abstention_reason=None,
        verified_evidence=[e1, e2],
        confidence_penalty=0.15,
    )
    assert decision.is_verified is True
    assert decision.is_abstained is False
    # Mean confidence = (0.8 + 0.6) / 2 = 0.70; 0.70 - 0.15 = 0.55
    assert abs(decision.effective_confidence - 0.55) < 1e-4

    # Abstained case must yield 0.0 effective confidence
    abstained_decision = VerificationDecision(
        status=VerificationStatus.ABSTAINED,
        abstained=True,
        abstention_reason="NO_EVIDENCE_PRODUCED: test",
        verified_evidence=[],
        confidence_penalty=0.0,
    )
    assert abstained_decision.is_abstained is True
    assert abstained_decision.is_verified is False
    assert abstained_decision.effective_confidence == 0.0


def test_verification_decision_as_pipeline_tuple():
    ev = [_evidence(confidence=0.9)]
    decision = VerificationDecision(
        status=VerificationStatus.VERIFIED,
        abstained=False,
        abstention_reason=None,
        verified_evidence=ev,
    )
    unpacked_ev, abstained, reason = decision.as_pipeline_tuple()
    assert unpacked_ev == ev
    assert abstained is False
    assert reason is None


# ---------------------------------------------------------------------------
# 2. Rule 01: Empty Evidence Gate
# ---------------------------------------------------------------------------
def test_rule_01_empty_evidence_gate():
    is_abstained, reason = evaluate_empty_evidence([])
    assert is_abstained is True
    assert AbstentionReasonCode.NO_EVIDENCE_PRODUCED in str(reason)

    ev = [_evidence()]
    is_abstained, reason = evaluate_empty_evidence(ev)
    assert is_abstained is False
    assert reason is None


def test_verify_empty_evidence():
    decision = verify([])
    assert decision.is_abstained is True
    assert decision.status == VerificationStatus.ABSTAINED
    assert AbstentionReasonCode.NO_EVIDENCE_PRODUCED in str(decision.abstention_reason)
    assert decision.verified_evidence == []
    assert decision.effective_confidence == 0.0


# ---------------------------------------------------------------------------
# 3. Rule 02: Confidence Floor Gate
# ---------------------------------------------------------------------------
def test_rule_02_all_subfloor_abstains():
    ev1 = _evidence(confidence=0.15, ev_id="ev-low-1")
    ev2 = _evidence(confidence=0.25, ev_id="ev-low-2")

    surviving, filtered_ids, is_subfloor, reason = evaluate_confidence_floor([ev1, ev2], 0.30)
    assert is_subfloor is True
    assert surviving == []
    assert filtered_ids == ["ev-low-1", "ev-low-2"]
    assert AbstentionReasonCode.INSUFFICIENT_CONFIDENCE in str(reason)


def test_rule_02_partial_subfloor_filters_low_confidence():
    ev1 = _evidence(confidence=0.20, ev_id="ev-low")
    ev2 = _evidence(confidence=0.75, ev_id="ev-high")

    surviving, filtered_ids, is_subfloor, reason = evaluate_confidence_floor([ev1, ev2], 0.30)
    assert is_subfloor is False
    assert len(surviving) == 1
    assert surviving[0].id == "ev-high"
    assert filtered_ids == ["ev-low"]
    assert reason is None


def test_verify_confidence_floor_filtering():
    ev1 = _evidence(confidence=0.10, ev_id="ev-1")
    ev2 = _evidence(confidence=0.85, ev_id="ev-2")

    decision = verify([ev1, ev2])
    assert decision.is_verified is True
    assert len(decision.verified_evidence) == 1
    assert decision.verified_evidence[0].id == "ev-2"
    assert decision.filtered_evidence_ids == ["ev-1"]


# ---------------------------------------------------------------------------
# 4. Rule 03: Sensor Physical Incompatibility Gate
# ---------------------------------------------------------------------------
def test_rule_03_sensor_compatibility():
    sar_img = ImageInput(id="img-s1", modality=Modality.SAR, format="GeoTIFF")
    opt_img = ImageInput(id="img-s2", modality=Modality.OPTICAL, format="GeoTIFF")

    # Incompatible query on SAR-only image
    is_incompat, reason = evaluate_sensor_compatibility(
        "Calculate NDVI and check green vegetation color",
        [sar_img],
    )
    assert is_incompat is True
    assert AbstentionReasonCode.SENSOR_PHYSICAL_LIMITATION in str(reason)

    # Compatible query on SAR-only image
    is_incompat, reason = evaluate_sensor_compatibility(
        "Measure microwave surface roughness and flood extent",
        [sar_img],
    )
    assert is_incompat is False
    assert reason is None

    # Spectral query on Optical image is valid
    is_incompat, reason = evaluate_sensor_compatibility(
        "Calculate NDVI and check green vegetation color",
        [opt_img],
    )
    assert is_incompat is False
    assert reason is None

    # Spectral query on multimodal (SAR + Optical) image is valid
    is_incompat, reason = evaluate_sensor_compatibility(
        "Calculate NDVI and check green vegetation color",
        [sar_img, opt_img],
    )
    assert is_incompat is False
    assert reason is None


def test_verify_sensor_physical_limitation():
    sar_img = ImageInput(id="img-s1", modality=Modality.SAR, format="GeoTIFF")
    ev = [_evidence(confidence=0.9)]

    decision = verify(
        evidence=ev,
        raw_query="What is the natural color and NDVI reflectance of this terrain?",
        images=[sar_img],
    )
    assert decision.is_abstained is True
    assert AbstentionReasonCode.SENSOR_PHYSICAL_LIMITATION in str(decision.abstention_reason)
    assert len(decision.disagreements) == 1
    assert decision.disagreements[0].category == DisagreementCategory.SENSOR_PHYSICAL_LIMITATION


# ---------------------------------------------------------------------------
# 5. Rule 04: Cloud vs. SAR Radar Reconciliation
# ---------------------------------------------------------------------------
def test_rule_04_cloud_sar_reconciliation():
    opt_ev = _evidence(
        payload={"cloud_fraction": 0.65, "optical_inconclusive": True},
        confidence=0.5,
        ev_id="opt-cloud",
    )
    sar_ev = _evidence(
        payload={"water_mask": [[1, 1], [0, 0]], "water_fraction": 0.45},
        confidence=0.85,
        ev_id="sar-water",
    )

    records = evaluate_cloud_sar_reconciliation([opt_ev, sar_ev])
    assert len(records) == 1
    rec = records[0]
    assert rec.rule_id == "RULE-VERIFY-04"
    assert rec.category == DisagreementCategory.COMPLEMENTARY_OBSERVATION
    assert rec.action_taken == "reconciled"
    assert "opt-cloud" in rec.conflicting_evidence_ids


def test_verify_preserves_sar_under_cloud_cover_without_abstaining():
    opt_ev = _evidence(
        payload={"cloud_fraction": 0.70, "optical_inconclusive": True},
        confidence=0.5,
        ev_id="opt-cloud",
    )
    sar_ev = _evidence(
        payload={"water_mask": "valid_mask", "water_fraction": 0.40},
        confidence=0.90,
        ev_id="sar-water",
    )

    decision = verify([opt_ev, sar_ev])
    assert decision.is_verified is True
    assert decision.is_abstained is False
    assert len(decision.verified_evidence) == 2
    assert any(d.rule_id == "RULE-VERIFY-04" for d in decision.disagreements)


# ---------------------------------------------------------------------------
# 6. Rule 06: Structured Numeric Grounding
# ---------------------------------------------------------------------------
def test_rule_06_numeric_grounding_penalty_when_contradicted():
    policy = VerificationPolicy(unsupported_numeric_penalty=0.15)
    stats_ev = _evidence(
        ev_type=EvidenceType.STATS,
        payload={"water_fraction": 0.25, "area_km2": 45.0},
        confidence=0.9,
    )
    text_ev = _evidence(
        ev_type=EvidenceType.TEXT,
        payload={"text": "Analysis shows water_fraction: 0.85 across the area."},
        confidence=0.8,
        ev_id="text-claim",
    )

    records, penalty = evaluate_structured_numeric_grounding([stats_ev, text_ev], policy)
    assert len(records) == 1
    assert records[0].category == DisagreementCategory.UNSUPPORTED_NUMERIC_CLAIM
    assert records[0].action_taken == "downgraded"
    assert abs(penalty - 0.15) < 1e-4


def test_rule_06_numeric_grounding_passes_when_supported():
    policy = VerificationPolicy()
    stats_ev = _evidence(
        ev_type=EvidenceType.STATS,
        payload={"water_fraction": 0.35},
        confidence=0.9,
    )
    text_ev = _evidence(
        ev_type=EvidenceType.TEXT,
        payload={"text": "Observed water_fraction: 0.35 in basin."},
        confidence=0.85,
    )

    records, penalty = evaluate_structured_numeric_grounding([stats_ev, text_ev], policy)
    assert len(records) == 0
    assert penalty == 0.0


# ---------------------------------------------------------------------------
# 7. Rule Conflict: Irreconcilable Cross-Modal Contradiction
# ---------------------------------------------------------------------------
def test_rule_conflict_severe_contradiction():
    policy = VerificationPolicy()
    opt_ev = _evidence(
        payload={
            "modality": "optical",
            "region": "sector_A",
            "cloud_fraction": 0.0,
            "optical_inconclusive": False,
            "water_fraction": 0.0,
        },
        confidence=0.9,
        ev_id="opt-clear",
    )
    sar_ev = _evidence(
        payload={
            "modality": "sar",
            "region": "sector_A",
            "water_fraction": 0.90,
        },
        confidence=0.9,
        ev_id="sar-water",
    )

    is_severe, reason, records, penalty = evaluate_cross_modal_conflict(
        [opt_ev, sar_ev],
        None,
        policy,
    )
    assert is_severe is True
    assert AbstentionReasonCode.SEVERE_MODALITY_CONFLICT in str(reason)
    assert len(records) == 1
    assert records[0].action_taken == "abstained"
    assert penalty == policy.severe_conflict_penalty


# ---------------------------------------------------------------------------
# 8. Trace Generation & Serialization
# ---------------------------------------------------------------------------
def test_verification_trace_params_serialization():
    ev = _evidence(confidence=0.8)
    decision = VerificationDecision(
        status=VerificationStatus.VERIFIED,
        abstained=False,
        abstention_reason=None,
        verified_evidence=[ev],
        disagreements=[
            DisagreementRecord(
                rule_id="RULE-VERIFY-04",
                category=DisagreementCategory.COMPLEMENTARY_OBSERVATION,
                description="Observation is complementary.",
                action_taken="reconciled",
                conflicting_evidence_ids=["opt-1"],
            )
        ],
        confidence_penalty=0.10,
        filtered_evidence_ids=["filtered-1"],
    )

    params = verification_trace_params(decision)
    assert params["status"] == "verified"
    assert params["abstained"] is False
    assert params["abstention_reason"] is None
    assert params["confidence_penalty"] == 0.10
    assert params["effective_confidence"] == 0.70
    assert params["retained_evidence_count"] == 1
    assert params["filtered_evidence_count"] == 1
    assert params["filtered_evidence_ids"] == ["filtered-1"]
    assert params["disagreement_count"] == 1
    assert len(params["disagreements"]) == 1
    assert params["disagreements"][0]["category"] == "complementary_observation"


def test_create_verification_trace_step():
    ev = _evidence(confidence=0.85)
    decision = VerificationDecision(
        status=VerificationStatus.VERIFIED,
        abstained=False,
        abstention_reason=None,
        verified_evidence=[ev],
    )
    started = datetime.now(UTC)
    step = create_verification_trace_step(decision, started_at=started)

    assert step.module == "verification"
    assert step.action == "verify"
    assert step.confidence == 0.85
    assert step.evidence_ids == [ev.id]
    assert step.params["status"] == "verified"
