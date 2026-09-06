import io
import pytest
from app.evidence.report import generate_evidence_pdf
from fastapi.testclient import TestClient
from app.api.main import app


def test_generate_evidence_pdf_creates_valid_stream():
    sample_data = {
        "query_id": "test-query-123",
        "verdict": "Confirmed Change",
        "confidence": "0.94",
        "summary": "Building footprint increased in sector 4B.",
        "citations": [
            {"id": "c1", "source": "Sentinel-2", "confidence": "0.95", "detail": "Pixel contrast delta detected"}
        ],
    }
    buf = generate_evidence_pdf(sample_data)
    assert isinstance(buf, io.BytesIO)
    content = buf.getvalue()
    assert content.startswith(b"%PDF-")


def test_export_evidence_pdf_endpoint():
    client = TestClient(app)
    response = client.post(
        "/api/evidence/export-pdf",
        json={"query_id": "test-456", "verdict": "Unchanged", "confidence": "0.99"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")
