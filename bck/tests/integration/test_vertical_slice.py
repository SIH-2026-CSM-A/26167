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
    assert body["abstained"] is False
    assert body["evidence"][0]["payload"]["raw_model_answer"] != body["text"]
    assert body["text"] == "A river is visible."
    assert "industrial pollution" not in body["text"].lower()
    assert any(step["action"] == "verification_completed" for step in body["trace"]["steps"])
