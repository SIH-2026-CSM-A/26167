from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.contracts import (
    Answer,
    Evidence,
    EvidenceType,
    ExecutionTrace,
    ImageInput,
    Modality,
    QueryRequest,
    TraceStep,
)


def _evidence() -> Evidence:
    return Evidence(
        id="ev-1",
        tool="vqa_grounding",
        type=EvidenceType.BBOX,
        payload={"bbox": [0, 0, 10, 10]},
        confidence=0.9,
        timing=0.42,
    )


def _trace() -> ExecutionTrace:
    step = TraceStep(
        module="router",
        action="classify",
        started_at=datetime.now(UTC),
        evidence_ids=["ev-1"],
    )
    return ExecutionTrace(trace_id="tr-1", steps=[step], created_at=datetime.now(UTC))


def test_query_request_round_trip():
    image = ImageInput(id="img-1", modality=Modality.OPTICAL, format="GeoTIFF")
    req = QueryRequest(query="what is this?", images=[image])
    assert req.images[0].modality is Modality.OPTICAL


def test_query_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        QueryRequest(query="")


def test_evidence_confidence_bounds():
    with pytest.raises(ValidationError):
        Evidence(id="e", tool="t", type=EvidenceType.TEXT, payload={}, confidence=1.5, timing=0.0)


def test_evidence_rejects_unknown_type():
    with pytest.raises(ValidationError):
        Evidence(id="e", tool="t", type="not-a-real-type", payload={}, confidence=0.5, timing=0.0)


def test_answer_requires_reason_when_abstained():
    with pytest.raises(ValidationError):
        Answer(text="", trace=_trace(), confidence=0.0, abstained=True)


def test_answer_forbids_reason_when_not_abstained():
    with pytest.raises(ValidationError):
        Answer(
            text="ok",
            trace=_trace(),
            confidence=0.8,
            abstained=False,
            abstention_reason="unused",
        )


def test_answer_valid_abstention():
    answer = Answer(
        text="",
        evidence=[],
        trace=_trace(),
        confidence=0.0,
        abstained=True,
        abstention_reason="insufficient evidence to support a claim",
    )
    assert answer.abstained is True
