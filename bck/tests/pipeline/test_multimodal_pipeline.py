"""End-to-end multi-image and multi-modal pipeline integration tests.

Covers the six mandatory SIH query and routing scenarios:
- Scenario A: Single optical VQA ("What is visible in this image?")
- Scenario B: Bi-temporal change detection ("What changed between these scenes?")
- Scenario C: Optical + SAR cross-modal fusion ("Identify flooded areas using both optical and SAR")
- Scenario D: Cloudy optical with SAR fusion (SAR preserved, F22 degradation notice attached)
- Scenario E: Change detection query with 1 image (Router veto 422)
- Scenario F: Fusion query without SAR image (Router veto 422)
"""

from pathlib import Path

import numpy as np
import pytest

from app.contracts import EvidenceType, Modality
from app.pipeline import PipelineError, PipelineUpload, run
from tests.helpers import (
    DeterministicChangeDetector,
    DeterministicVqaModel,
    make_geotiff_bytes,
    make_sar_geotiff_bytes,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
S1_FIXTURE = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
S2_FIXTURE = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"


def test_scenario_a_single_optical_vqa() -> None:
    """Scenario A: 1 optical image and question 'What is visible in this image?' routes to VQA."""
    upload = PipelineUpload(
        id="opt-scene",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible in this image?",
        uploads=[upload],
        model=DeterministicVqaModel(answer="A river and forest.", grounding="A river and forest."),
    )

    assert answer.abstained is False
    assert "river" in answer.text.lower()
    assert "forest" in answer.text.lower()
    assert len(answer.evidence) == 1
    assert answer.evidence[0].tool == "internvl_vqa"

    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "vqa_grounding"
    assert route_step.params["intent"] == "vqa"


def test_scenario_b_change_detection_bitemporal() -> None:
    """Scenario B: 2 optical images and 'What changed' routes to BIT change detection."""
    upload_pre = PipelineUpload(
        id="t1-pre",
        filename="pre_event.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    upload_post = PipelineUpload(
        id="t2-post",
        filename="post_event.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    detector = DeterministicChangeDetector(changed=True, change_fraction=0.35, confidence=0.92)
    answer = run(
        query="What changed between these scenes?",
        uploads=[upload_pre, upload_post],
        change_detector=detector,
    )

    assert answer.abstained is False
    assert "Change detected across 35.0% of the scene" in answer.text
    assert len(answer.evidence) == 1
    ev = answer.evidence[0]
    assert ev.type is EvidenceType.MASK
    assert ev.tool == "change_detection.bit"
    assert ev.payload["source_image_a_id"] == "t1-pre"
    assert ev.payload["source_image_b_id"] == "t2-post"
    assert np.isclose(answer.confidence, 0.92)

    actions = [step.action for step in answer.trace.steps]
    assert "change_detection_started" in actions
    assert "change_detection_completed" in actions
    assert "verification_completed" in actions

    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "change_detection"
    assert route_step.params["intent"] == "change_vqa"


def test_scenario_c_optical_sar_fusion() -> None:
    """Scenario C: Optical + SAR pair asking flood analysis routes to cross-modal fusion."""
    upload_opt = PipelineUpload(
        id="opt-1",
        filename="optical.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    upload_sar = PipelineUpload(
        id="sar-1",
        filename="sar.tif",
        content_type="image/tiff",
        content=make_sar_geotiff_bytes(shape=(16, 16)),
        modality=Modality.SAR,
    )

    answer = run(
        query="Identify flooded areas using both optical and SAR imagery.",
        uploads=[upload_opt, upload_sar],
    )

    assert answer.abstained is False
    assert "water coverage" in answer.text.lower()
    assert len(answer.evidence) >= 1
    ev = answer.evidence[0]
    assert ev.type is EvidenceType.MASK
    assert ev.tool == "fusion.reconcile"
    assert ev.payload["source_optical_id"] == "opt-1"
    assert ev.payload["source_sar_id"] == "sar-1"

    actions = [step.action for step in answer.trace.steps]
    assert "fusion_started" in actions
    assert "fusion_completed" in actions
    assert "verification_completed" in actions

    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "fusion"
    assert route_step.params["intent"] == "fusion"


def test_scenario_d_cloudy_optical_with_sar_fusion(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario D: Cloudy optical + SAR preserves SAR flood evidence and attaches F22 notice."""
    if not S1_FIXTURE.exists() or not S2_FIXTURE.exists():
        pytest.skip("Sen1Floods11 fixtures not present")

    monkeypatch.setenv("SATQUERY_CLOUD_DEGRADATION_THRESHOLD", "0.01")

    upload_opt = PipelineUpload(
        id="opt-s2",
        filename="Bolivia_103757_S2Hand.tif",
        content_type="image/tiff",
        content=S2_FIXTURE.read_bytes(),
        modality=Modality.OPTICAL,
    )
    upload_sar = PipelineUpload(
        id="sar-s1",
        filename="Bolivia_103757_S1Hand.tif",
        content_type="image/tiff",
        content=S1_FIXTURE.read_bytes(),
        modality=Modality.SAR,
    )

    answer = run(
        query="Identify flooded areas using both optical and SAR imagery.",
        uploads=[upload_opt, upload_sar],
    )

    assert answer.abstained is False
    assert len(answer.evidence) >= 1
    assert answer.degradation_notice is not None
    assert answer.degradation_notice.degraded is True
    assert answer.degradation_notice.metric_value > 0.01
    assert answer.degradation_notice.fallback_modality == Modality.SAR
    assert "SAR-only fallback" in answer.degradation_notice.suggested_action

    degradation_events = [
        s for s in answer.trace.steps
        if s.module == "quality" and s.action == "degradation_detected"
    ]
    assert len(degradation_events) == 1

    actions = [step.action for step in answer.trace.steps]
    assert "fusion_started" in actions
    assert "fusion_completed" in actions
    assert "verification_completed" in actions


def test_scenario_e_change_detection_single_image_veto() -> None:
    """Scenario E: Change detection query with only 1 image triggers clear router veto (422)."""
    upload = PipelineUpload(
        id="single-scene",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    with pytest.raises(PipelineError) as exc_info:
        run(
            query="What changed between these scenes?",
            uploads=[upload],
            model=DeterministicVqaModel(answer="none", grounding="none"),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.stage == "routing"
    assert "requires 2 temporal images" in exc_info.value.message


def test_scenario_f_fusion_missing_sar_veto() -> None:
    """Scenario F: Fusion query without SAR image triggers clear router veto (422)."""
    upload_opt1 = PipelineUpload(
        id="opt-1",
        filename="scene1.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    upload_opt2 = PipelineUpload(
        id="opt-2",
        filename="scene2.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    with pytest.raises(PipelineError) as exc_info:
        run(
            query="Perform cross-modal optical and SAR joint analysis.",
            uploads=[upload_opt1, upload_opt2],
            model=DeterministicVqaModel(answer="none", grounding="none"),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.stage == "routing"
    assert "requires both Optical and SAR" in exc_info.value.message
