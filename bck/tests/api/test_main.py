"""Multipart API integration tests for the real vertical-slice orchestration."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.db.models import Base
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes

client = TestClient(app)


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


@pytest.fixture(autouse=True)
def deterministic_model() -> Iterator[None]:
    """Replace only heavyweight inference while exercising every real surrounding layer."""
    app.state.vqa_model = DeterministicVqaModel(
        answer="A river is visible.", grounding="A river is visible in the scene."
    )
    yield
    del app.state.vqa_model


def test_query_accepts_real_multipart_geotiff() -> None:
    """A valid multipart GeoTIFF request must return the canonical verified answer."""
    response = client.post(
        "/query",
        data={"query": "What feature is visible?", "modality": ["optical"]},
        files=[("images", ("scene.tif", make_geotiff_bytes(), "image/tiff"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["abstained"] is False
    assert body["text"] == "A river is visible."
    assert body["evidence"][0]["payload"]["source_filename"] == "scene.tif"
    assert body["trace"]["steps"][-1]["action"] == "response_completed"


def test_query_requires_non_whitespace_question() -> None:
    """Whitespace-only questions must fail request validation."""
    response = client.post(
        "/query",
        data={"query": "   ", "modality": ["optical"]},
        files=[("images", ("scene.tif", make_geotiff_bytes(), "image/tiff"))],
    )

    assert response.status_code == 422
    assert "query" in str(response.json()["detail"]).lower()


def test_query_requires_an_uploaded_image() -> None:
    """Multipart validation must reject a query without an image."""
    response = client.post("/query", data={"query": "Describe this image"})

    assert response.status_code == 422
    assert "images" in str(response.json()["detail"]).lower()


def test_query_rejects_unsupported_file() -> None:
    """A non-TIFF upload must return a useful media-type error."""
    response = client.post(
        "/query",
        data={"query": "Describe this image", "modality": ["optical"]},
        files=[("images", ("scene.png", b"png", "image/png"))],
    )

    assert response.status_code == 415
    assert response.json()["detail"]["stage"] == "ingestion"


def test_query_rejects_unreadable_tiff() -> None:
    """Unreadable TIFF bytes must produce a handled validation response."""
    response = client.post(
        "/query",
        data={"query": "Describe this image", "modality": ["optical"]},
        files=[("images", ("broken.tiff", b"not-a-tiff", "image/tiff"))],
    )

    assert response.status_code == 422
    assert response.json()["detail"]["stage"] == "ingestion"
