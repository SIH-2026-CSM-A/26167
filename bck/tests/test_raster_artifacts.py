"""Tests for shared host/container raster artifacts."""

import numpy as np

from app.contracts import ImageInput, Modality
from app.core import raster_artifacts


def test_mask_artifact_returns_container_titiler_url(tmp_path, monkeypatch) -> None:
    """A georeferenced mask is persisted under the shared volume path."""
    monkeypatch.setattr(raster_artifacts, "HOST_RASTER_DIR", tmp_path)
    monkeypatch.setattr(
        raster_artifacts,
        "get_cog_tile_url",
        lambda path: f"http://127.0.0.1:8001/cog/tiles/{{z}}/{{x}}/{{y}}?url={path}",
    )
    source = ImageInput(
        id="source",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="source.tif",
        metadata={
            "crs": "EPSG:4326",
            "transform": [0.01, 0, 10, 0, -0.01, 20],
            "width": 4,
            "height": 4,
        },
    )

    url = raster_artifacts.write_mask_artifact(np.ones((4, 4), dtype=bool), source)

    assert url is not None
    assert "/data/rasters/" in url
    assert len(list(tmp_path.glob("*.tif"))) == 1
