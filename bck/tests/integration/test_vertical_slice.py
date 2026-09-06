"""API-style proof that verification participates in the complete request path."""

from fastapi.testclient import TestClient

from app.api.main import app
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes


def test_live_api_path_removes_an_unsupported_model_claim() -> None:
    """The full API path must return verified text rather than the raw hallucinated answer."""
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
    assert body["evidence"][0]["payload"]["raw_model_answer"] != body["text"]
    assert body["text"] == "A river is visible."
    assert "industrial pollution" not in body["text"].lower()
    assert any(step["action"] == "verification_completed" for step in body["trace"]["steps"])
