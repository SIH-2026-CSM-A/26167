from collections.abc import Iterator
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import Modality
from app.db.models import Base
from app.pipeline import PipelineUpload, run
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes


@pytest.fixture(autouse=True)
def sqlite_db() -> Iterator[None]:
    """Provide an in-memory SQLite database sessionmaker for pipeline persistence."""
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


def test_pipeline_verifies_model_output_and_builds_evidence_and_trace() -> None:
    """Canonical verification evaluates tool output and builds auditable trace."""
    model = DeterministicVqaModel(
        answer="A river is visible and industrial pollution is contaminating the water.",
        grounding="A river is visible in the scene.",
    )
    upload = PipelineUpload(
        id="asset-1",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    answer = run(
        query="What geographic feature is visible?",
        uploads=[upload],
        model=model,
    )

    assert answer.text == "A river is visible."
    assert answer.text != answer.evidence[0].payload["raw_model_answer"]
    assert "pollution" not in answer.text.lower()
    assert answer.abstained is False
    assert answer.evidence[0].payload["source_asset_id"] == "asset-1"
    actions = [step.action for step in answer.trace.steps]
    assert actions == [
        "request_received",
        "asset_received",
        "asset_ingestion_started",
        "asset_ingested",
        "routing_started",
        "route_selected",
        "vqa_started",
        "internvl_inference_started",
        "internvl_inference_completed",
        "verification_started",
        "verification_completed",
        "evidence_created",
        "response_completed",
    ]
    verification_step = next(
        step for step in answer.trace.steps if step.action == "verification_completed"
    )
    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "vqa_grounding"
    assert verification_step.params["status"] == "verified"
    assert verification_step.params["retained_evidence_count"] == 1
    assert verification_step.params["rejected_claim_count"] == 1
