"""B4: modality trust boundary, end-to-end through pipeline.run().

No live Postgres: persistence is stubbed the same way
tests/pipeline/test_pipeline.py already stubs it.
"""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from rasterio.io import MemoryFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import Modality
from app.db.models import Base
from app.pipeline import PipelineError, PipelineUpload, run

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
S2_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"

# Same canonical query text as tests/router/test_router.py's PS_QUERY_4.
PS_QUERY_4 = (
    "Use the optical and SAR images together to identify built-up and water-covered regions."
)


def _make_ambiguous_geotiff_bytes() -> bytes:
    """Structurally valid GeoTIFF with no band descriptions/tags/RGB colorinterp."""
    with MemoryFile() as memory_file:
        with memory_file.open(driver="GTiff", width=4, height=3, count=2, dtype="uint8"):
            pass
        return memory_file.read()


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


def test_omitted_modality_classifies_real_sar_and_optical_and_still_dispatches_fusion():
    """No client-supplied modality at all: both real images classify correctly from metadata."""
    if not S1_PATH.exists() or not S2_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixtures not present under {FIXTURES_DIR}")

    sar_upload = PipelineUpload(
        id="sar-1",
        filename="Bolivia_103757_S1Hand.tif",
        content_type="image/tiff",
        content=S1_PATH.read_bytes(),
        modality=None,
    )
    optical_upload = PipelineUpload(
        id="optical-1",
        filename="Bolivia_103757_S2Hand.tif",
        content_type="image/tiff",
        content=S2_PATH.read_bytes(),
        modality=None,
    )

    answer = run(query=PS_QUERY_4, uploads=[sar_upload, optical_upload])

    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "fusion"
    assert route_step.params["supported"] is True


def test_unknown_modality_triggers_clarification_before_any_tool_runs():
    """Ambiguous metadata -> UNKNOWN -> typed veto/clarification, no tool trace step at all."""
    ambiguous_upload = PipelineUpload(
        id="ambiguous-1",
        filename="ambiguous.tif",
        content_type="image/tiff",
        content=_make_ambiguous_geotiff_bytes(),
        modality=None,
    )

    with pytest.raises(PipelineError) as excinfo:
        run(query="What is visible in this image?", uploads=[ambiguous_upload])

    assert excinfo.value.status_code == 422
    assert excinfo.value.stage == "routing"
    assert "Optical or SAR" in excinfo.value.message

    actions = [step.action for step in excinfo.value.trace.steps]
    assert "route_selected" in actions
    assert "execution_failed" in actions
    # No tool-execution step of any kind reached — the whole point of B4 item 4.
    tool_actions = {"vqa_started", "change_detection_started", "fusion_started"}
    assert tool_actions.isdisjoint(actions)


def test_client_supplied_modality_override_is_recorded_in_trace_metadata():
    """The existing client-supplied `modality` path is used as-is and recorded, not re-guessed."""
    override_upload = PipelineUpload(
        id="override-1",
        filename="ambiguous.tif",
        content_type="image/tiff",
        content=_make_ambiguous_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    answer = run(query="What is visible in this image?", uploads=[override_upload])

    ingested_step = next(step for step in answer.trace.steps if step.action == "asset_ingested")
    assert ingested_step.params["source_metadata"][0]["modality_source"] == "client_override"
