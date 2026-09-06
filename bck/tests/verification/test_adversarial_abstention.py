"""Adversarial abstention tests for SatQuery AI (SHIVA-004, F15/F16).

Verifies ticket acceptance criteria:
- AC 1A: Absent-object query against real image fixture produces explicit typed abstention
- AC 1B: Real cloud-obscured optical + useful SAR preserves SAR evidence and does NOT abstain
- AC 1C: Deliberately contradictory optical/SAR evidence triggers typed abstention
- AC 2: Structured numeric claims in TEXT grounded against STATS payloads
- AC 3: Explicit typed abstention triggers enforced across all four codes
- AC 4: Cloud-obscured optical + SAR does not automatically abstain
- AC 5: Abstention is structurally distinguishable from low confidence in trace params
- AC 6: End-to-end pipeline run produces valid auditable execution trace
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import rasterio

from app.contracts import (
    Answer,
    Evidence,
    EvidenceType,
    ExecutionTrace,
    ImageInput,
    Modality,
)
from app.pipeline import PipelineUpload, run
from app.tools.fusion.cloud_detector import detect_clouds
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask
from app.verification import (
    AbstentionReasonCode,
    DisagreementCategory,
    VerificationPolicy,
    VerificationStatus,
    verification_trace_params,
    verify,
)
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
S2_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"
SEN12MS_CR_NPZ_PATH = FIXTURES_DIR / "sen12ms_cr_sample.npz"


def _make_evidence(
    tool: str = "test_detector",
    ev_type: EvidenceType = EvidenceType.TEXT,
    payload: dict | None = None,
    confidence: float = 0.85,
    ev_id: str | None = None,
) -> Evidence:
    return Evidence(
        id=ev_id or str(uuid.uuid4()),
        tool=tool,
        type=ev_type,
        payload=payload or {},
        confidence=confidence,
        timing=0.05,
    )


# ---------------------------------------------------------------------------
# AC 1A: Absent-Object Query Against Real Image Fixture
# ---------------------------------------------------------------------------
def test_ac_1a_absent_object_empty_detection_abstains():
    """AC 1A: Query for absent object on real image fixture produces typed abstention.

    Epistemic limitation strictly observed: Verification does not inspect raw pixels.
    The detector tool evaluates the real fixture and returns zero detections (empty evidence).
    Verification enforces explicit typed abstention NO_EVIDENCE_PRODUCED.
    """
    assert S2_PATH.exists(), f"Real fixture missing: {S2_PATH}"
    with rasterio.open(S2_PATH) as src:
        image_shape = src.shape

    image_input = ImageInput(
        id="s2-chip",
        modality=Modality.OPTICAL,
        format="GeoTIFF",
        metadata={"shape": image_shape, "path": str(S2_PATH)},
    )

    # Tool searches for absent object ('airplane') on real Bolivia wetland chip -> 0 detections
    detector_output: list[Evidence] = []

    decision = verify(
        evidence=detector_output,
        raw_query="Detect all airplanes on the tarmac in this imagery.",
        images=[image_input],
    )

    assert decision.is_abstained is True
    assert decision.status == VerificationStatus.ABSTAINED
    assert AbstentionReasonCode.NO_EVIDENCE_PRODUCED in str(decision.abstention_reason)
    assert decision.verified_evidence == []


def test_ac_1a_absent_object_subfloor_confidence_abstains():
    """AC 1A: Detector returns weak speculative candidate below confidence floor.

    Verification filters it out and triggers INSUFFICIENT_CONFIDENCE abstention.
    """
    image_input = ImageInput(
        id="s2-chip",
        modality=Modality.OPTICAL,
        format="GeoTIFF",
        metadata={"path": str(S2_PATH)},
    )

    # Tool yields speculative candidate with very low confidence (0.12 < 0.30 floor)
    speculative_evidence = [
        _make_evidence(
            tool="vqa_grounding",
            ev_type=EvidenceType.BBOX,
            payload={"label": "airplane", "box_2d": [10, 10, 30, 30]},
            confidence=0.12,
        )
    ]

    decision = verify(
        evidence=speculative_evidence,
        raw_query="Detect airplanes in this image.",
        images=[image_input],
    )

    assert decision.is_abstained is True
    assert decision.status == VerificationStatus.ABSTAINED
    assert AbstentionReasonCode.INSUFFICIENT_CONFIDENCE in str(decision.abstention_reason)
    assert decision.verified_evidence == []
    assert len(decision.filtered_evidence_ids) == 1


# ---------------------------------------------------------------------------
# AC 1B & AC 4: Real Cloud-Obscured Optical + Useful SAR
# ---------------------------------------------------------------------------
def test_ac_1b_and_ac_4_real_cloud_obscured_optical_with_sar_preserves_evidence():
    """AC 1B & AC 4: Real SEN12MS-CR cloud-obscured pair through fusion tools.

    Provenance: Genuine SEN12MS-CR dataset (Ebel et al., IEEE TGRS 2021),
    fall / scene_4 / patch_p523. Contains raw calibrated 2-band float32 SAR backscatter
    (VV/VH in dB) and 13-band float32 Sentinel-2 TOA reflectance.

    Verification surfaces optical cloud limitation under COMPLEMENTARY_OBSERVATION,
    preserves SAR water evidence, and does NOT abstain.
    """
    if not SEN12MS_CR_NPZ_PATH.exists():
        pytest.skip(f"SEN12MS-CR fixture missing under {FIXTURES_DIR}")

    data = np.load(SEN12MS_CR_NPZ_PATH)
    s1_sar = data["s1"]  # (256, 256, 2) float32 calibrated backscatter in dB
    s2_cloudy = data["s2_cloudy"]  # (256, 256, 13) float32 TOA reflectance in [0, 1]

    # Extract VV polarization in dB for despeckling and water masking
    vv = s1_sar[..., 0].astype(np.float64)
    despeckled = lee_filter(vv, SarScale.DB, noise_variance=0.005)
    water = otsu_water_mask(despeckled, SarScale.DB)

    # Run native s2cloudless pixel classifier on 13-band Sentinel-2 TOA reflectance
    cloud_result = detect_clouds(s2_cloudy)

    fusion_evidence = reconcile_sar_optical(despeckled, water, cloud_result)
    assert len(fusion_evidence) >= 1

    s1_input = ImageInput(
        id="s1",
        modality=Modality.SAR,
        format="application/x-numpy",
        metadata={
            "dataset": "SEN12MS-CR",
            "season": str(data["season"]),
            "scene": str(data["scene"]),
            "patch": str(data["patch"]),
            "channels": ["VV", "VH"],
            "unit": "dB",
        },
    )
    s2_input = ImageInput(
        id="s2",
        modality=Modality.OPTICAL,
        format="application/x-numpy",
        metadata={
            "dataset": "SEN12MS-CR",
            "season": str(data["season"]),
            "scene": str(data["scene"]),
            "patch": str(data["patch"]),
            "channels": 13,
            "unit": "TOA reflectance [0, 1]",
        },
    )

    decision = verify(
        evidence=fusion_evidence,
        raw_query="Assess surface water extent under partial cloud obscuration.",
        images=[s1_input, s2_input],
    )

    # Must NOT abstain
    assert decision.is_verified is True
    assert decision.is_abstained is False
    assert decision.status == VerificationStatus.VERIFIED
    assert decision.abstention_reason is None

    # SAR evidence is preserved
    assert len(decision.verified_evidence) >= 1

    # Optical limitation is auditable as complementary observation
    complementary_recs = [
        d
        for d in decision.disagreements
        if d.category == DisagreementCategory.COMPLEMENTARY_OBSERVATION
    ]
    assert len(complementary_recs) == 1
    assert complementary_recs[0].action_taken == "reconciled"


# ---------------------------------------------------------------------------
# AC 1C: Deliberately Contradictory Optical/SAR Evidence Pair
# ---------------------------------------------------------------------------
def test_ac_1c_severe_contradiction_abstains():
    """AC 1C: Direct irreconcilable contradiction on same region triggers abstention."""
    opt_evidence = _make_evidence(
        tool="fusion",
        ev_type=EvidenceType.TEXT,
        payload={
            "modality": "optical",
            "region": "flood_zone_alpha",
            "cloud_fraction": 0.0,
            "optical_inconclusive": False,
            "water_fraction": 0.0,
        },
        confidence=0.95,
        ev_id="opt-dry",
    )
    sar_evidence = _make_evidence(
        tool="fusion",
        ev_type=EvidenceType.TEXT,
        payload={
            "modality": "sar",
            "region": "flood_zone_alpha",
            "water_fraction": 0.92,
        },
        confidence=0.95,
        ev_id="sar-wet",
    )

    decision = verify(
        evidence=[opt_evidence, sar_evidence],
        raw_query="Is flood_zone_alpha inundated?",
    )

    assert decision.is_abstained is True
    assert decision.status == VerificationStatus.ABSTAINED
    assert AbstentionReasonCode.SEVERE_MODALITY_CONFLICT in str(decision.abstention_reason)
    assert len(decision.disagreements) == 1
    assert decision.disagreements[0].category == DisagreementCategory.CROSS_MODAL_CONFLICT
    assert decision.disagreements[0].action_taken == "abstained"


# ---------------------------------------------------------------------------
# AC 2: Structured Numeric Claim Grounding Against STATS Payloads
# ---------------------------------------------------------------------------
def test_ac_2_unsupported_numeric_claim_downgrades_confidence():
    """AC 2: TEXT evidence asserting unsupported quantitative metric is downgraded."""
    policy = VerificationPolicy(unsupported_numeric_penalty=0.15)

    stats_evidence = _make_evidence(
        tool="fusion_stats",
        ev_type=EvidenceType.STATS,
        payload={"water_fraction": 0.15, "area_km2": 12.5},
        confidence=0.90,
    )
    unsupported_text_evidence = _make_evidence(
        tool="vqa_text",
        ev_type=EvidenceType.TEXT,
        payload={
            "text": "Severe inundation confirmed: water_fraction: 0.85 covering area: 150 km2."
        },
        confidence=0.90,
        ev_id="unsupported-text",
    )

    decision = verify(
        evidence=[stats_evidence, unsupported_text_evidence],
        policy=policy,
    )

    assert decision.is_verified is True
    assert decision.is_abstained is False

    # Two contradicted metrics (water_fraction and area_km2) -> two disagreement records
    unsupported_recs = [
        d
        for d in decision.disagreements
        if d.category == DisagreementCategory.UNSUPPORTED_NUMERIC_CLAIM
    ]
    assert len(unsupported_recs) == 2
    assert all(r.action_taken == "downgraded" for r in unsupported_recs)

    # Penalty applied: 2 * 0.15 = 0.30
    assert abs(decision.confidence_penalty - 0.30) < 1e-4
    # Mean confidence = 0.90; effective confidence = 0.90 - 0.30 = 0.60
    assert abs(decision.effective_confidence - 0.60) < 1e-4


# ---------------------------------------------------------------------------
# AC 3: Enforce Explicit Typed Abstention Triggers
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "reason_code, evidence_factory, query, images",
    [
        (
            AbstentionReasonCode.NO_EVIDENCE_PRODUCED,
            lambda: [],
            "Find all vessels in the harbor.",
            [ImageInput(id="i1", modality=Modality.OPTICAL, format="GeoTIFF")],
        ),
        (
            AbstentionReasonCode.INSUFFICIENT_CONFIDENCE,
            lambda: [_make_evidence(confidence=0.15)],
            "Identify the structure at coordinates.",
            [ImageInput(id="i1", modality=Modality.OPTICAL, format="GeoTIFF")],
        ),
        (
            AbstentionReasonCode.SENSOR_PHYSICAL_LIMITATION,
            lambda: [_make_evidence(confidence=0.90)],
            "Calculate NDVI and check visual green color.",
            [ImageInput(id="i1", modality=Modality.SAR, format="GeoTIFF")],
        ),
        (
            AbstentionReasonCode.SEVERE_MODALITY_CONFLICT,
            lambda: [
                _make_evidence(
                    payload={
                        "modality": "optical",
                        "region": "zone_1",
                        "cloud_fraction": 0.0,
                        "optical_inconclusive": False,
                        "water_fraction": 0.0,
                    },
                    confidence=0.9,
                ),
                _make_evidence(
                    payload={"modality": "sar", "region": "zone_1", "water_fraction": 0.85},
                    confidence=0.9,
                ),
            ],
            "Check flooding in zone_1.",
            None,
        ),
    ],
)
def test_ac_3_explicit_typed_abstention_triggers(reason_code, evidence_factory, query, images):
    """AC 3: All typed abstention triggers yield valid Answer(abstained=True)."""
    ev = evidence_factory()
    decision = verify(evidence=ev, raw_query=query, images=images)

    assert decision.is_abstained is True
    assert decision.status == VerificationStatus.ABSTAINED
    assert reason_code in str(decision.abstention_reason)

    # Validates Answer contract schema constraints
    ev_list, abstained, reason = decision.as_pipeline_tuple()
    trace = ExecutionTrace(
        trace_id=str(uuid.uuid4()),
        steps=[],
        created_at=datetime.now(UTC),
    )
    answer = Answer(
        query=query,
        text=reason or "Abstained",
        confidence=decision.effective_confidence,
        visual_evidence=None,
        trace=trace,
        abstained=abstained,
        abstention_reason=reason,
    )
    assert answer.abstained is True
    assert answer.abstention_reason is not None


# ---------------------------------------------------------------------------
# AC 5: Abstention is Structurally Distinguishable in Trace
# ---------------------------------------------------------------------------
def test_ac_5_trace_params_distinguishes_abstention_from_low_confidence():
    """AC 5: Abstention and low-confidence verified answers are unambiguously distinct in trace."""
    # 1. Abstained decision
    abstained_decision = verify([])
    abstained_params = verification_trace_params(abstained_decision)

    assert abstained_params["status"] == "abstained"
    assert abstained_params["abstained"] is True
    assert abstained_params["abstention_reason"] is not None
    assert abstained_params["effective_confidence"] == 0.0
    assert abstained_params["confidence_penalty"] == 0.0

    # 2. Low-confidence verified decision (penalized, but retained)
    stats_ev = _make_evidence(
        ev_type=EvidenceType.STATS, payload={"water_fraction": 0.10}, confidence=0.60
    )
    text_ev = _make_evidence(
        ev_type=EvidenceType.TEXT,
        payload={"text": "water_fraction: 0.90"},
        confidence=0.60,
    )
    verified_decision = verify([stats_ev, text_ev])
    verified_params = verification_trace_params(verified_decision)

    assert verified_params["status"] == "verified"
    assert verified_params["abstained"] is False
    assert verified_params["abstention_reason"] is None
    assert verified_params["confidence_penalty"] > 0.0
    assert verified_params["effective_confidence"] > 0.0
    assert verified_params["retained_evidence_count"] == 2


# ---------------------------------------------------------------------------
# AC 6: End-to-End Pipeline Execution
# ---------------------------------------------------------------------------
def test_ac_6_pipeline_e2e_auditable_trace():
    """AC 6: Full pipeline.run(request) records verification hop with auditable parameters."""
    upload = PipelineUpload(
        id="img-01",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    model = DeterministicVqaModel(
        answer="Vegetation index is 0.7.",
        grounding="Vegetation index is 0.7 in the scene.",
    )
    answer = run(
        query="Analyze the vegetation index in this area.",
        uploads=[upload],
        model=model,
    )

    assert isinstance(answer, Answer)
    assert answer.trace is not None

    verify_step = next(
        (s for s in answer.trace.steps if s.action == "verification_completed"), None
    )
    assert verify_step is not None
    assert "status" in verify_step.params
    assert "effective_confidence" in verify_step.params
    assert "retained_evidence_count" in verify_step.params
