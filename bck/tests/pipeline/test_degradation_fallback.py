"""Focused pipeline integration tests for F22 degradation detection and fallback signal."""

from pathlib import Path

import numpy as np
import pytest

import app.pipeline.pipeline as app_pipeline
from app.contracts import Modality
from app.pipeline import PipelineUpload, run
from app.router import route as real_route
from app.tools.fusion.cloud_detector import CloudDetectionResult
from tests.helpers import (
    DeterministicVqaModel,
    make_geotiff_bytes,
    make_sar_geotiff_bytes,
)

S2_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "Bolivia_103757_S2Hand.tif"


def test_pipeline_rgb_never_calls_detect_clouds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.pipeline.pipeline.detect_clouds",
        lambda *a, **k: pytest.fail("detect_clouds must never be called for 3-band RGB"),
    )
    upload = PipelineUpload(
        id="rgb-1", filename="scene.tif", content_type="image/tiff",
        content=make_geotiff_bytes(), modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?", uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )
    assert answer.degradation_notice is None
    assert answer.abstained is False


def test_pipeline_13_band_input_detects_once_and_creates_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[np.ndarray] = []
    mask = np.zeros((10, 10), dtype=bool)
    mask[:5, :] = True

    def _mock_detect(reflectance: np.ndarray) -> CloudDetectionResult:
        calls.append(reflectance)
        return CloudDetectionResult(probability=mask.astype(np.float32), mask=mask)

    monkeypatch.setattr("app.pipeline.pipeline.detect_clouds", _mock_detect)

    upload = PipelineUpload(
        id="s2-cloudy", filename="Bolivia_103757_S2Hand.tif", content_type="image/tiff",
        content=S2_FIXTURE_PATH.read_bytes(), modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?", uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )

    assert len(calls) == 1
    notice = answer.degradation_notice
    assert notice is not None and notice.degraded is True
    assert notice.metric_name == "cloud_cover_fraction"
    assert np.isclose(notice.metric_value, 0.50)
    assert np.isclose(notice.threshold, 0.20)
    assert notice.fallback_modality == Modality.SAR
    assert notice.affected_image_ids == ["s2-cloudy"]
    assert "SAR-only fallback" in notice.suggested_action

    trace_events = [
        s for s in answer.trace.steps
        if s.module == "quality" and s.action == "degradation_detected"
    ]
    assert len(trace_events) == 1


def test_pipeline_reuses_existing_cloud_fraction_without_recomputation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        id="opt-cached", filename="scene.tif", content_type="image/tiff",
        content=make_geotiff_bytes(), modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?", uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )

    assert answer.degradation_notice is not None
    assert answer.degradation_notice.metric_value == 0.85


def test_pipeline_multiple_degraded_inputs_uses_max_and_single_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fractions = {"opt-1": 0.30, "opt-2": 0.70}
    original_ingest = app_pipeline.ingest_raster

    def _wrapped_ingest(upload):
        ingested = original_ingest(upload)
        ingested.source.metadata["cloud_fraction"] = fractions[upload.id]
        return ingested

    monkeypatch.setattr("app.pipeline.pipeline.ingest_raster", _wrapped_ingest)
    monkeypatch.setattr(
        "app.pipeline.pipeline.route",
        lambda req: real_route(req.model_copy(update={"images": req.images[:1]})),
    )

    uploads = [
        PipelineUpload(
            id=uid, filename=f"{uid}.tif", content_type="image/tiff",
            content=make_geotiff_bytes(), modality=Modality.OPTICAL,
        )
        for uid in ("opt-1", "opt-2")
    ]
    answer = run(
        query="What is visible?", uploads=uploads,
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )

    assert answer.degradation_notice is not None
    assert answer.degradation_notice.metric_value == 0.70
    assert set(answer.degradation_notice.affected_image_ids) == {"opt-1", "opt-2"}

    trace_events = [
        s for s in answer.trace.steps
        if s.module == "quality" and s.action == "degradation_detected"
    ]
    assert len(trace_events) == 1


def test_pipeline_clean_cloud_fraction_below_threshold_produces_no_notice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_ingest = app_pipeline.ingest_raster

    def _wrapped_ingest(upload):
        ingested = original_ingest(upload)
        ingested.source.metadata["cloud_fraction"] = 0.05
        return ingested

    monkeypatch.setattr("app.pipeline.pipeline.ingest_raster", _wrapped_ingest)

    upload = PipelineUpload(
        id="opt-clean", filename="scene.tif", content_type="image/tiff",
        content=make_geotiff_bytes(), modality=Modality.OPTICAL,
    )
    answer = run(
        query="What is visible?", uploads=[upload],
        model=DeterministicVqaModel(answer="River", grounding="River"),
    )

    assert answer.degradation_notice is None
    assert answer.abstained is False
    assert "River" in answer.text
    assert not any(
        s.module == "quality" and s.action == "degradation_detected"
        for s in answer.trace.steps
    )
def test_pipeline_fusion_13_band_detects_clouds_once_and_reuses_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F22: cloud detection is computed once and reused by fusion."""
    if not S2_FIXTURE_PATH.exists():
        pytest.skip("Sentinel-2 fixture not present")

    calls: list[np.ndarray] = []
    original_detect_clouds = app_pipeline.detect_clouds

    def _counting_detect(reflectance: np.ndarray) -> CloudDetectionResult:
        calls.append(reflectance)
        return original_detect_clouds(reflectance)

    monkeypatch.setattr(
        "app.pipeline.pipeline.detect_clouds",
        _counting_detect,
    )

    upload_opt = PipelineUpload(
        id="opt-s2",
        filename="Bolivia_103757_S2Hand.tif",
        content_type="image/tiff",
        content=S2_FIXTURE_PATH.read_bytes(),
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
    assert len(answer.evidence) >= 1

    assert len(calls) == 1