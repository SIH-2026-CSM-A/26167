from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_query_builds_answer_from_uploaded_image():
    response = client.post(
        "/query",
        data={"query": "what crop is this?", "modality": ["optical"]},
        files=[("images", ("scene.tif", b"fake-tiff-bytes", "image/tiff"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert "what crop is this?" in body["text"]
    assert len(body["evidence"]) == 1


def test_query_rejects_mismatched_images_and_modality():
    response = client.post(
        "/query",
        data={"query": "q", "modality": ["optical", "sar"]},
        files=[("images", ("scene.tif", b"bytes", "image/tiff"))],
    )

    assert response.status_code == 422


def test_query_rejects_no_images():
    response = client.post("/query", data={"query": "q"})

    assert response.status_code == 422
