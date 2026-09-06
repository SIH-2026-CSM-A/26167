"""Automated tests for trace and evidence persistence, models, and failure semantics."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts import Evidence, EvidenceType, ExecutionTrace, Modality, TraceStep
from app.db.models import Base, EvidenceModel, ExecutionTraceModel
from app.db.persistence import TracePersistenceError, persist_trace
from app.pipeline import PipelineError, PipelineUpload, run
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes


@pytest.fixture
def sqlite_session() -> Session:
    """Provide an isolated, in-memory SQLite database session for unit tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_maker()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_models_cascade_delete(sqlite_session: Session) -> None:
    """Deleting an ExecutionTrace cascades to delete its associated Evidence records."""
    trace_id = str(uuid.uuid4())
    trace = ExecutionTraceModel(
        trace_id=trace_id,
        created_at=datetime.now(UTC),
        steps=[{"module": "test", "action": "step1"}],
    )
    evidence = EvidenceModel(
        id=str(uuid.uuid4()),
        trace_id=trace_id,
        tool="test_tool",
        type="text",
        payload={"result": "found"},
        confidence=0.9,
        timing=0.1,
    )
    sqlite_session.add(trace)
    sqlite_session.add(evidence)
    sqlite_session.commit()

    saved_trace = sqlite_session.scalar(
        select(ExecutionTraceModel).where(ExecutionTraceModel.trace_id == trace_id)
    )
    assert saved_trace is not None
    assert len(saved_trace.evidence) == 1

    sqlite_session.delete(saved_trace)
    sqlite_session.commit()

    saved_evidence = sqlite_session.scalar(
        select(EvidenceModel).where(EvidenceModel.trace_id == trace_id)
    )
    assert saved_evidence is None


def test_persist_trace_roundtrip(sqlite_session: Session) -> None:
    """Persisted execution trace and evidence deserialize faithfully to original contract data."""
    now = datetime.now(UTC)
    trace_id = str(uuid.uuid4())
    steps = [
        TraceStep(
            module="pipeline",
            action="request_received",
            params={"query": "test query"},
            started_at=now,
            completed_at=now,
        ),
        TraceStep(
            module="router",
            action="route_selected",
            params={"tool": "vqa_grounding"},
            confidence=0.95,
            started_at=now,
            completed_at=now,
        ),
    ]
    trace = ExecutionTrace(
        trace_id=trace_id,
        steps=steps,
        created_at=now,
    )
    evidence_id = str(uuid.uuid4())
    evidence = Evidence(
        id=evidence_id,
        tool="internvl_vqa",
        type=EvidenceType.TEXT,
        payload={"answer": "detected water body", "metadata": {"band": "B8"}},
        confidence=0.88,
        timing=0.045,
    )

    persist_trace(trace, [evidence], session=sqlite_session)
    sqlite_session.commit()

    persisted_trace = sqlite_session.scalar(
        select(ExecutionTraceModel).where(ExecutionTraceModel.trace_id == trace_id)
    )
    assert persisted_trace is not None
    assert persisted_trace.trace_id == trace_id
    assert len(persisted_trace.steps) == 2
    assert persisted_trace.steps[0]["action"] == "request_received"
    assert persisted_trace.steps[1]["confidence"] == 0.95

    persisted_ev = sqlite_session.scalar(
        select(EvidenceModel).where(EvidenceModel.id == evidence_id)
    )
    assert persisted_ev is not None
    assert persisted_ev.trace_id == trace_id
    assert persisted_ev.tool == "internvl_vqa"
    assert persisted_ev.type == "text"
    assert persisted_ev.payload == {"answer": "detected water body", "metadata": {"band": "B8"}}
    assert persisted_ev.confidence == 0.88
    assert persisted_ev.timing == 0.045


def test_persist_trace_abstained_empty_evidence(sqlite_session: Session) -> None:
    """Abstained pipeline execution persists the trace with an empty evidence list."""
    now = datetime.now(UTC)
    trace_id = str(uuid.uuid4())
    trace = ExecutionTrace(
        trace_id=trace_id,
        steps=[
            TraceStep(
                module="pipeline",
                action="request_received",
                started_at=now,
            ),
            TraceStep(
                module="verification",
                action="execution_failed",
                params={"reason": "cloud cover exceeds threshold"},
                started_at=now,
            ),
        ],
        created_at=now,
    )

    persist_trace(trace, [], session=sqlite_session)
    sqlite_session.commit()

    persisted_trace = sqlite_session.scalar(
        select(ExecutionTraceModel).where(ExecutionTraceModel.trace_id == trace_id)
    )
    assert persisted_trace is not None
    assert len(persisted_trace.evidence) == 0


def test_extensibility_multiple_tool_payloads(sqlite_session: Session) -> None:
    """Diverse tool evidence payloads persist without requiring schema migrations."""
    now = datetime.now(UTC)
    trace_id = str(uuid.uuid4())
    trace = ExecutionTrace(trace_id=trace_id, steps=[], created_at=now)

    evidence_items = [
        Evidence(
            id=str(uuid.uuid4()),
            tool="change_detection",
            type=EvidenceType.STATS,
            payload={"change_ratio": 0.35, "area_km2": 12.4},
            confidence=0.91,
            timing=0.12,
        ),
        Evidence(
            id=str(uuid.uuid4()),
            tool="vqa_grounding",
            type=EvidenceType.BBOX,
            payload={"box_2d": [10, 20, 100, 200], "label": "reservoir"},
            confidence=0.85,
            timing=0.08,
        ),
        Evidence(
            id=str(uuid.uuid4()),
            tool="fusion",
            type=EvidenceType.LAYER,
            payload={
                "layer_url": "https://titiler.internal/cog/tiles/1/2/3",
                "bands": ["B4", "B3", "B2"],
            },
            confidence=0.99,
            timing=0.02,
        ),
    ]

    persist_trace(trace, evidence_items, session=sqlite_session)
    sqlite_session.commit()

    rows = sqlite_session.scalars(
        select(EvidenceModel).where(EvidenceModel.trace_id == trace_id)
    ).all()
    assert len(rows) == 3
    tools = {r.tool for r in rows}
    assert tools == {"change_detection", "vqa_grounding", "fusion"}


def test_persist_trace_raises_on_db_failure(sqlite_session: Session) -> None:
    """Persistence failure raises TracePersistenceError."""
    now = datetime.now(UTC)
    trace = ExecutionTrace(trace_id="t1", steps=[], created_at=now)

    with patch.object(sqlite_session, "add", side_effect=RuntimeError("disk write error")):
        with pytest.raises(TracePersistenceError, match="Database persistence failed"):
            persist_trace(trace, [], session=sqlite_session)


def test_pipeline_raises_hard_failure_on_persistence_error() -> None:
    """A DB write failure on persistence raises PipelineError
    with stage='persistence' and status_code=500.
    """
    model = DeterministicVqaModel(
        answer="A lake is visible.",
        grounding="A lake is visible in the scene.",
    )
    upload = PipelineUpload(
        id="asset-test",
        filename="test.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    with patch(
        "app.pipeline.pipeline.persist_trace",
        side_effect=TracePersistenceError("Database disk full"),
    ):
        with pytest.raises(PipelineError) as exc_info:
            run(
                query="What geographic feature is visible?",
                uploads=[upload],
                model=model,
            )

    err = exc_info.value
    assert err.stage == "persistence"
    assert err.status_code == 500
    assert "Database disk full" in err.message
    # Check that partial trace recorded the failure step
    last_step = err.trace.steps[-1]
    assert last_step.module == "persistence"
    assert last_step.action == "execution_failed"
    assert "Database disk full" in str(last_step.params.get("message"))
