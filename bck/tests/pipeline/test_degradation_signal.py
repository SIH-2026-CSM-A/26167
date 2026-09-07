"""Focused pipeline tests for SHIVA-006 / F22 optical cloud degradation signal & fallback."""

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

import app.pipeline.pipeline as app_pipeline
from app.contracts import Modality
from app.pipeline import PipelineUpload, run
from app.verification import evaluate_optical_degradation
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes

S2_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "Bolivia_103757_S2Hand.tif"


@pytest.fixture(autouse=True)
def _disable_persistence():
    """Keep degradation-signal tests independent of database configuration."""
    with patch("app.pipeline.pipeline.persist_trace"):
        yield


def test_pipeline_real_bolivia_fixture_clean_under_default_threshold() -> None:
    """AC4 / AC2: Real unmocked Sentinel-2 Bolivia fixture has measured cloud_fraction

    of ~0.018711 (1.87%), which is below default threshold 0.20, so NO degradation notice
    is produced. Real s2cloudless detect_clouds runs without mocking.
    """
    assert S2_FIXTURE_PATH.exists(), f"Real fixture missing at {S2_FIXTURE_PATH}"

    upload = PipelineUpload(
        id="s2-bolivia",
        filename="Bolivia_103757_S2Hand.tif",
        content_type="image/tiff",
        content=S2_FIXTURE_PATH.read_bytes(),
        modality=Modality.OPTICAL,
    )
    answer = run(
        query="What features are present in this satellite scene?",
        uploads=[upload],
        model=DeterministicVqaModel(
            answer="River and vegetation.",
            grounding="River and vegetation.",
        ),
    )

    assert answer.abstained is False
    assert answer.degradation_notice is None
    assert not any(
        s.module == "quality" and s.action == "degradation_detected" for s in answer.trace.steps
    )


def test_pipeline_real_bolivia_fixture_degrades_when_threshold_lowered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC4 / AC1: Real unmocked Sentinel-2 Bolivia fixture (~0.0187 cloud) exceeds threshold

    when threshold is set to 0.01 via SATQUERY_CLOUD_DEGRADATION_THRESHOLD.
    Real s2cloudless runs without mocking, emitting structured DegradationNotice.
    """
    assert S2_FIXTURE_PATH.exists(), f"Real fixture missing at {S2_FIXTURE_PATH}"
    monkeypatch.setenv("SATQUERY_CLOUD_DEGRADATION_THRESHOLD", "0.01")

    upload = PipelineUpload(
        id="s2-bolivia",
        filename="Bolivia_103757_S2Hand.tif",
        content_type="image/tiff",
        content=S2_FIXTURE_PATH.read_bytes(),
        modality=Modality.OPTICAL,
    )
    answer = run(
        query="What features are present in this satellite scene?",
        uploads=[upload],
        model=DeterministicVqaModel(
            answer="River and vegetation.",
            grounding="River and vegetation.",
        ),
    )

    notice = answer.degradation_notice
    assert notice is not None
    assert notice.degraded is True
    assert notice.metric_name == "cloud_cover_fraction"
    assert np.isclose(notice.metric_value, 0.0187, atol=0.001)
    assert np.isclose(notice.threshold, 0.01, atol=0.001)
    assert notice.severity == "warning"
    assert notice.fallback_modality == Modality.SAR
    assert notice.affected_image_ids == ["s2-bolivia"]
    assert "SAR-only fallback" in notice.suggested_action
    assert "1.9%" in notice.message or "1.8%" in notice.message

    trace_events = [
        s
        for s in answer.trace.steps
        if s.module == "quality" and s.action == "degradation_detected"
    ]
    assert len(trace_events) == 1
    assert trace_events[0].params["degraded"] is True
    assert trace_events[0].params["fallback_modality"] == "sar"


def test_pipeline_reuses_existing_cloud_fraction_without_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC3: Precomputed cloud_fraction in source metadata is reused without calling
    detect_clouds.
    """
    monkeypatch.setattr(
        "app.pipeline.pipeline.detect_clouds",
        lambda *a, **k: pytest.fail("detect_clouds must not be called when cloud_fraction exists"),
    )
    original_ingest = app_pipeline.ingest_raster

    def _wrapped_ingest(upload):
        ingested = original_ingest(upload)
        ingested.source.metadata["cloud_fraction"] = 0.85
        return ingested

    monkeypatch.setattr("app.pipeline.pipeline.ingest_raster", _wrapped_ingest)

    upload = PipelineUpload(
        id="opt-cached",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?",
        uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )

    assert answer.degradation_notice is not None
    assert answer.degradation_notice.metric_value == 0.85


def test_pipeline_rgb_never_calls_detect_clouds(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC3 / AC4: Standard 3-band RGB imagery never invokes Sentinel-2 10/13-band detect_clouds."""
    monkeypatch.setattr(
        "app.pipeline.pipeline.detect_clouds",
        lambda *a, **k: pytest.fail("detect_clouds must never be called for 3-band RGB"),
    )
    upload = PipelineUpload(
        id="rgb-1",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?",
        uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )
    assert answer.degradation_notice is None
    assert answer.abstained is False


def test_pipeline_clean_cloud_fraction_below_threshold_produces_no_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean optical input with injected fraction below threshold produces no notice."""
    original_ingest = app_pipeline.ingest_raster

    def _wrapped_ingest(upload):
        ingested = original_ingest(upload)
        ingested.source.metadata["cloud_fraction"] = 0.05
        return ingested

    monkeypatch.setattr("app.pipeline.pipeline.ingest_raster", _wrapped_ingest)

    upload = PipelineUpload(
        id="opt-clean",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?",
        uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )

    assert answer.degradation_notice is None
    assert answer.abstained is False
    assert not any(
        s.module == "quality" and s.action == "degradation_detected" for s in answer.trace.steps
    )


def test_evaluate_optical_degradation_unit() -> None:
    """Direct unit tests for evaluate_optical_degradation rule in app.verification."""
    from app.contracts import ImageInput

    assert evaluate_optical_degradation([]) is None
    assert evaluate_optical_degradation(None) is None

    sar_img = ImageInput(id="sar-1", modality=Modality.SAR, format="GTiff", path="sar.tif")
    assert evaluate_optical_degradation([sar_img]) is None

    clean_opt = ImageInput(
        id="opt-1",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="opt1.tif",
        metadata={"cloud_fraction": 0.0187},
    )
    assert evaluate_optical_degradation([clean_opt], threshold=0.20) is None

    cloudy_opt = ImageInput(
        id="opt-2",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="opt2.tif",
        metadata={"cloud_fraction": 0.45},
    )
    notice = evaluate_optical_degradation([clean_opt, cloudy_opt], threshold=0.20)
    assert notice is not None
    assert notice.degraded is True
    assert notice.metric_value == 0.45
    assert notice.threshold == 0.20
    assert notice.affected_image_ids == ["opt-2"]
