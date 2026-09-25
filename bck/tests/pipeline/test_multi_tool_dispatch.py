"""F7/F11: change-detection and fusion dispatch wiring, end-to-end through pipeline.run().

Uses the real Sentinel-1/Sentinel-2 Bolivia_103757 fixtures for fusion — this
is the exact "q4" scenario the B1 fix targeted (101,623 finite / 160,521 NaN
pixels, irregular SAR footprint), confirmed directly against these files
below. No live Postgres: persistence is stubbed the same way
tests/pipeline/test_pipeline.py already stubs it.
"""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import Modality
from app.db.models import Base
from app.inference.remote import RemoteChangeResult
from app.pipeline import PipelineError, PipelineUpload, run
from app.tools.change_detection.bit_io import encode_mask_png, encode_probability_png

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
S2_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"
LEVIR_T1_PATH = FIXTURES_DIR / "levir_test_1_t1.png"
LEVIR_T2_PATH = FIXTURES_DIR / "levir_test_1_t2.png"


@pytest.fixture(autouse=True)
def sqlite_db() -> Iterator[None]:
    """In-memory SQLite standing in for Postgres, same pattern as test_pipeline.py."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    with patch("app.db.session.get_sync_session_maker", return_value=session_maker):
        yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_exact_q4_fixture_confirms_the_real_irregular_nan_footprint():
    """Sanity-anchor: this is the real scene B1's ticket described, not a synthetic stand-in."""
    if not S1_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present under {FIXTURES_DIR}")
    with rasterio.open(S1_PATH) as dataset:
        vv = dataset.read(1).astype(np.float64)
    assert vv.size == 262144
    assert int(np.isfinite(vv).sum()) == 101623
    assert int(np.isnan(vv).sum()) == 160521


def test_fusion_dispatch_end_to_end_produces_real_evidence():
    """q4: real SAR+optical pair with a large irregular NaN footprint reaches fusion.reconcile."""
    if not S1_PATH.exists() or not S2_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixtures not present under {FIXTURES_DIR}")

    sar_upload = PipelineUpload(
        id="sar-1",
        filename="Bolivia_103757_S1Hand.tif",
        content_type="image/tiff",
        content=S1_PATH.read_bytes(),
        modality=Modality.SAR,
    )
    optical_upload = PipelineUpload(
        id="optical-1",
        filename="Bolivia_103757_S2Hand.tif",
        content_type="image/tiff",
        content=S2_PATH.read_bytes(),
        modality=Modality.OPTICAL,
    )

    answer = run(
        query="Fuse the optical and SAR imagery to identify flooding.",
        uploads=[sar_upload, optical_upload],
    )

    assert answer.evidence, "fusion produced no evidence at all"
    for evidence in answer.evidence:
        assert evidence.tool == "fusion.reconcile"
        assert evidence.payload["valid_pixel_count"] == 101623
        assert evidence.payload["invalid_pixel_count"] == 160521
        assert np.isclose(evidence.payload["support_fraction"], 101623 / 262144)
        assert "water_mask" in evidence.payload
        assert "valid_mask" in evidence.payload

    actions = [step.action for step in answer.trace.steps]
    assert "fusion_started" in actions
    assert "fusion_inference_completed" in actions
    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "fusion"
    assert route_step.params["intent"] == "fusion"


def _levir_uploads() -> list[PipelineUpload]:
    from io import BytesIO

    from PIL import Image

    def _png_to_tiff_bytes(png_path: Path) -> bytes:
        buffer = BytesIO()
        Image.open(png_path).convert("RGB").save(buffer, format="TIFF")
        return buffer.getvalue()

    return [
        PipelineUpload(
            id="pre-1",
            filename="levir_test_1_t1.tif",
            content_type="image/tiff",
            content=_png_to_tiff_bytes(LEVIR_T1_PATH),
            modality=Modality.OPTICAL,
            capture_order=0,
        ),
        PipelineUpload(
            id="post-1",
            filename="levir_test_1_t2.tif",
            content_type="image/tiff",
            content=_png_to_tiff_bytes(LEVIR_T2_PATH),
            modality=Modality.OPTICAL,
            capture_order=1,
        ),
    ]


def test_change_detection_dispatch_sends_bit_inputs_to_the_space_and_builds_evidence_here():
    """q3/q5: a real bi-temporal LEVIR pair reaches change detection; BIT itself is remote.

    The Space is mocked: it returns a fixed-scale probability map with a known changed
    square. Gating, confidence, summary and the trace are computed by the real code here.
    """
    if not LEVIR_T1_PATH.exists() or not LEVIR_T2_PATH.exists():
        pytest.skip(f"real LEVIR-CD fixtures not present under {FIXTURES_DIR}")

    probability = np.full((256, 256), 0.1, dtype=np.float32)
    probability[100:140, 100:140] = 0.9
    sent_sizes: list[tuple[int, int]] = []

    def fake_change_detect(pre, post):
        sent_sizes.extend([pre.size, post.size])
        return RemoteChangeResult(
            probability_png=encode_probability_png(probability),
            mask_png=encode_mask_png(probability > 0.5),
            inference_seconds=0.25,
            total_seconds=0.3,
            model_identity={"base_model": "OpenGVLab/InternVL3-2B"},
        )

    with patch("app.pipeline.pipeline.remote.change_detect", side_effect=fake_change_detect):
        answer = run(query="What changed between these two images?", uploads=_levir_uploads())

    assert sent_sizes == [(256, 256), (256, 256)]
    assert answer.evidence, "change detection produced no evidence at all"
    for evidence in answer.evidence:
        assert evidence.tool == "change_detection.bit"
    actions = [step.action for step in answer.trace.steps]
    for action in (
        "change_detection_started",
        "remote_change_detect_call",
        "bit_forward_pass",
        "bit_inference_completed",
    ):
        assert action in actions
    forward = next(step for step in answer.trace.steps if step.action == "bit_forward_pass")
    assert forward.params["duration_s"] == 0.25
    assert (forward.completed_at - forward.started_at).total_seconds() == pytest.approx(0.25)


def test_change_detection_without_a_configured_space_fails_cleanly_with_a_reason_code(
    monkeypatch,
):
    if not LEVIR_T1_PATH.exists() or not LEVIR_T2_PATH.exists():
        pytest.skip(f"real LEVIR-CD fixtures not present under {FIXTURES_DIR}")
    from app.core.config import get_settings

    monkeypatch.delenv("INFERENCE_SPACE", raising=False)
    get_settings.cache_clear()
    try:
        with pytest.raises(PipelineError) as excinfo:
            run(query="What changed between these two images?", uploads=_levir_uploads())
    finally:
        get_settings.cache_clear()
    assert excinfo.value.status_code == 503
    assert excinfo.value.reason_code == "INFERENCE_UNAVAILABLE"
    assert excinfo.value.stage == "model_inference"
    actions = [step.action for step in excinfo.value.trace.steps]
    assert "change_detection_started" in actions
    assert "execution_failed" in actions
