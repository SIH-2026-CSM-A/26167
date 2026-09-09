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
from app.pipeline import PipelineError, PipelineUpload, run
from app.pipeline.pipeline import BIT_CHECKPOINT_PATH

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


def test_change_detection_dispatch_reaches_bit_or_fails_cleanly_not_with_a_raw_500():
    """q3/q5: real bi-temporal LEVIR pair reaches change_detection, however BIT itself behaves here.

    Verified from scratch, not assumed: this environment has no BIT_LEVIR
    checkpoint committed, so `detect_change` cannot actually run end to end —
    confirmed by BIT_CHECKPOINT_PATH not existing on disk. Either behavior is
    accepted here, but a raw unhandled exception / HTTP 500 is not: this
    proves the dispatch wiring reaches the tool and that whatever the tool
    does (succeed, or fail on a missing checkpoint) comes back as a clean,
    typed PipelineError, never a crash.
    """
    if not LEVIR_T1_PATH.exists() or not LEVIR_T2_PATH.exists():
        pytest.skip(f"real LEVIR-CD fixtures not present under {FIXTURES_DIR}")

    from io import BytesIO

    from PIL import Image

    def _png_to_tiff_bytes(png_path: Path) -> bytes:
        buffer = BytesIO()
        Image.open(png_path).convert("RGB").save(buffer, format="TIFF")
        return buffer.getvalue()

    pre_upload = PipelineUpload(
        id="pre-1",
        filename="levir_test_1_t1.tif",
        content_type="image/tiff",
        content=_png_to_tiff_bytes(LEVIR_T1_PATH),
        modality=Modality.OPTICAL,
    )
    post_upload = PipelineUpload(
        id="post-1",
        filename="levir_test_1_t2.tif",
        content_type="image/tiff",
        content=_png_to_tiff_bytes(LEVIR_T2_PATH),
        modality=Modality.OPTICAL,
    )

    query = "What changed between these two images?"

    if Path(BIT_CHECKPOINT_PATH).is_file():
        answer = run(query=query, uploads=[pre_upload, post_upload])
        assert answer.evidence, "change detection produced no evidence at all"
        for evidence in answer.evidence:
            assert evidence.tool == "change_detection.bit"
        actions = [step.action for step in answer.trace.steps]
        assert "change_detection_started" in actions
        assert "bit_inference_completed" in actions
    else:
        with pytest.raises(PipelineError) as excinfo:
            run(query=query, uploads=[pre_upload, post_upload])
        assert excinfo.value.status_code == 503
        assert excinfo.value.stage == "model_inference"
        actions = [step.action for step in excinfo.value.trace.steps]
        assert "change_detection_started" in actions
        assert "execution_failed" in actions
