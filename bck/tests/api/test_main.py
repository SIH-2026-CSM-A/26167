"""Multipart API integration tests for the real vertical-slice orchestration."""

import uuid as uuid_module
from collections.abc import Iterator
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.db.models import Base
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes

client = TestClient(app)


def make_unclassifiable_geotiff_bytes() -> bytes:
    """Single-band GeoTIFF with no SAR/optical band signal — classify_modality returns UNKNOWN."""
    band = np.array([[10, 20], [30, 40]], dtype=np.uint8)
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            width=2,
            height=2,
            count=1,
            dtype="uint8",
            crs="EPSG:4326",
            transform=from_origin(77.0, 13.0, 0.01, 0.01),
        ) as dataset:
            dataset.write(band, 1)
            dataset.colorinterp = (rasterio.enums.ColorInterp.gray,)
        return memory_file.read()


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
        files=[("images", ("scene.bmp", b"png", "image/bmp"))],
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


def test_query_change_vqa_without_capture_order_abstains() -> None:
    """Bi-temporal change requests with no capture_order signal must abstain, not
    silently guess pre/post from upload order (this is the Chat path)."""
    response = client.post(
        "/query",
        data={
            "query": "What changed between these two dates, and where did the change occur?",
            "modality": ["optical", "optical"],
        },
        files=[
            ("images", ("t1.tif", make_geotiff_bytes(), "image/tiff")),
            ("images", ("t2.tif", make_geotiff_bytes(), "image/tiff")),
        ],
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["reason_code"] == "TEMPORAL_ORDER_MISSING"


def test_query_change_detection_binds_pre_post_by_capture_order_not_upload_order() -> None:
    """Images uploaded post-then-pre must still bind pre_image/post_image by their
    explicit capture_order, not by multipart upload order."""
    fixed_ids = [uuid_module.UUID(int=1), uuid_module.UUID(int=2)]
    real_uuid4 = uuid_module.uuid4

    def _uuid4_sequence() -> Iterator[uuid_module.UUID]:
        # The request generates more uuids than just the two upload ids (trace id,
        # persisted-raster paths, ...) — only the first two (one per uploaded image,
        # in upload order) need to be pinned down for this test's assertions.
        yield from fixed_ids
        while True:
            yield real_uuid4()

    with patch("app.api.main.uuid.uuid4", side_effect=_uuid4_sequence()):
        response = client.post(
            "/query",
            data={
                "query": "What changed between these two dates, and where did the change occur?",
                "modality": ["optical", "optical"],
                "capture_order": ["1", "0"],
            },
            files=[
                ("images", ("post.tif", make_geotiff_bytes(), "image/tiff")),
                ("images", ("pre.tif", make_geotiff_bytes(), "image/tiff")),
            ],
        )

    # Whether a BIT checkpoint happens to be present in this environment or not,
    # dispatch itself must reach the tool with the correct pre/post binding — that's
    # recorded in "change_detection_started" regardless of what BIT does afterward.
    assert response.status_code in (200, 503)
    body = response.json()
    trace = body["trace"] if response.status_code == 200 else body["detail"]["trace"]
    steps = trace["steps"]
    started = next(step for step in steps if step["action"] == "change_detection_started")
    assert started["params"]["pre_image_id"] == str(fixed_ids[1])
    assert started["params"]["post_image_id"] == str(fixed_ids[0])


def test_query_veto_preserves_reason_code_and_suggested_action() -> None:
    """A MODALITY_UNKNOWN veto must surface reason_code/suggested_action,
    not just a flattened message."""
    response = client.post(
        "/query",
        data={"query": "What changed here?"},
        files=[("images", ("scene.tif", make_unclassifiable_geotiff_bytes(), "image/tiff"))],
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["reason_code"] == "MODALITY_UNKNOWN"
    assert detail["suggested_action"] == (
        "Re-upload with standard band descriptions (e.g. VV/VH for SAR, "
        "B1-B12/B8A for Sentinel-2 optical), or specify the modality explicitly "
        "in the request."
    )
