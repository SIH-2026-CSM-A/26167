"""Reusable real-raster and model-double helpers for vertical-slice tests."""

from __future__ import annotations

import numpy as np
import rasterio
from PIL import Image
from rasterio.io import MemoryFile
from rasterio.transform import from_origin


def make_geotiff_bytes() -> bytes:
    """Return a valid in-memory three-band GeoTIFF with deterministic geospatial metadata."""
    red = np.array([[10, 20, 30, 40], [50, 60, 70, 80], [90, 100, 110, 120]], dtype=np.uint8)
    green = np.flipud(red)
    blue = np.full_like(red, 25)
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            width=4,
            height=3,
            count=3,
            dtype="uint8",
            crs="EPSG:4326",
            transform=from_origin(77.0, 13.0, 0.01, 0.01),
            nodata=0,
        ) as dataset:
            dataset.write(np.stack([red, green, blue]))
            dataset.colorinterp = (
                rasterio.enums.ColorInterp.red,
                rasterio.enums.ColorInterp.green,
                rasterio.enums.ColorInterp.blue,
            )
        return memory_file.read()


class DeterministicVqaModel:
    """Stand in only for expensive inference while preserving the real model boundary."""

    model_id = "test/deterministic-vqa"
    device = "test"

    def __init__(self, answer: str, grounding: str) -> None:
        """Store deterministic outputs for answer and grounding passes."""
        self._answer = answer
        self._grounding = grounding

    def generate(self, image: Image.Image, prompt: str) -> str:
        """Return grounding only when the production grounding prompt is supplied."""
        assert image.mode == "RGB"
        if "Candidate answer:" in prompt:
            return self._grounding
        return self._answer
