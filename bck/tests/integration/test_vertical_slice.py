"""API-style proof that verification participates in the complete request path."""

from fastapi.testclient import TestClient

from app.api.main import app
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes


def test_live_api_path_abstains_on_uncalibrated_vqa_output() -> None:
    """The full API path evaluates uncalibrated VQA output and enforces typed abstention."""
    app.state.vqa_model = DeterministicVqaModel(
        answer="A river is visible and industrial pollution is contaminating the water.",
        grounding="A river is visible in the scene.",
    )
    try:
        response = TestClient(app).post(
            "/query",
            data={"query": "What is visible?", "modality": ["optical"]},
            files=[("images", ("scene.tif", make_geotiff_bytes(), "image/tiff"))],
        )
    finally:
        del app.state.vqa_model

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is True
    assert body["abstention_reason"] == (
        "INSUFFICIENT_CONFIDENCE: Evidence confidence falls below the reliability threshold (0.30)."
    )
    assert body["text"] == ""
    assert body["evidence"] == []
    assert any(step["action"] == "verification_completed" for step in body["trace"]["steps"])
    verification_step = next(
        step for step in body["trace"]["steps"] if step["action"] == "verification_completed"
    )
    assert verification_step["params"]["status"] == "abstained"
