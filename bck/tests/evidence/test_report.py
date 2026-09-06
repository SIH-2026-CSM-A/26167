"""Tests for evidence report generation (PDF and GeoJSON exports)."""

import io
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.contracts.schemas import (
    Answer,
    Evidence,
    EvidenceType,
    ExecutionTrace,
    TraceStep,
)
from app.evidence.report import generate_evidence_geojson, generate_evidence_pdf

Trace = ExecutionTrace


def _make_sample_answer() -> Answer:
    now = datetime.now(UTC)
    step = TraceStep(
        module="change_detection",
        action="detect_change",
        params={"threshold": 0.5, "modality": "optical"},
        confidence=0.92,
        started_at=now,
        completed_at=now,
        evidence_ids=["ev-001"],
    )
    trace = Trace(
        trace_id="tr-test-001",
        steps=[step],
        created_at=now,
    )
    ev = Evidence(
        id="ev-001",
        tool="s2_change_detector",
        type=EvidenceType.BBOX,
        payload={
            "description": "Building footprint expansion detected in sector 4B",
            "bbox": [77.5, 12.9, 77.6, 13.0],
        },
        confidence=0.94,
        timing=1.25,
    )
    return Answer(
        text="Vegetation clearing and construction detected in target sector.",
        evidence=[ev],
        trace=trace,
        confidence=0.94,
        abstained=False,
        abstention_reason=None,
    )


def test_generate_evidence_pdf_creates_valid_stream() -> None:
    answer = _make_sample_answer()
    buf = generate_evidence_pdf(answer)
    assert isinstance(buf, io.BytesIO)
    content = buf.getvalue()
    assert content.startswith(b"%PDF-")


def test_generate_evidence_geojson_contains_crs84() -> None:
    answer = _make_sample_answer()
    geojson_str, filename = generate_evidence_geojson(answer)
    assert "urn:ogc:def:crs:OGC:1.3:CRS84" in geojson_str
    assert filename == "evidence-tr-test-001.geojson"
    assert "ev-001" in geojson_str


def test_export_evidence_pdf_endpoint() -> None:
    answer = _make_sample_answer()
    client = TestClient(app)
    response = client.post(
        "/api/evidence/export-pdf",
        json=answer.model_dump(mode="json"),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
    assert "evidence-tr-test-001.pdf" in response.headers.get("content-disposition", "")


def test_export_evidence_geojson_endpoint() -> None:
    answer = _make_sample_answer()
    client = TestClient(app)
    response = client.post(
        "/api/evidence/export-geojson",
        json=answer.model_dump(mode="json"),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/geo+json"
    assert "urn:ogc:def:crs:OGC:1.3:CRS84" in response.text
    assert "evidence-tr-test-001.geojson" in response.headers.get("content-disposition", "")
