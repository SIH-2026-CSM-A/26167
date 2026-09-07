from __future__ import annotations

import uuid

import numpy as np
import rasterio
from PIL import Image
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

from app.contracts import Evidence, EvidenceType, ImageInput


def make_geotiff_bytes() -> bytes:
    """Return a valid three-band GeoTIFF with deterministic geospatial metadata."""
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


def make_sar_geotiff_bytes(
    shape: tuple[int, int] = (16, 16),
    base_val: float = -15.0,
) -> bytes:
    """Return a single-band GeoTIFF with deterministic SAR backscatter values in dB."""
    arr = np.full(shape, base_val, dtype=np.float32)
    # Add water region (lower backscatter) in the upper half
    arr[: shape[0] // 2, :] = -25.0
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            width=shape[1],
            height=shape[0],
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(77.0, 13.0, 0.01, 0.01),
        ) as dataset:
            dataset.write(arr, 1)
        return memory_file.read()


class DeterministicChangeDetector:
    """Stand in for expensive BIT inference in pipeline tests."""

    def __init__(
        self,
        *,
        changed: bool = True,
        change_fraction: float = 0.25,
        confidence: float = 0.90,
    ) -> None:
        self.changed = changed
        self.change_fraction = change_fraction
        self.confidence = confidence

    def __call__(self, image_a: ImageInput, image_b: ImageInput) -> list[Evidence]:
        mask = np.zeros((256, 256), dtype=bool)
        if self.changed:
            rows = int(256 * self.change_fraction)
            mask[:rows, :] = True
            desc = (
                f"Change detected across {self.change_fraction * 100:.1f}% of the scene, "
                "located upper."
            )
            bbox = (0, 0, rows, 256)
            rel = "upper"
        else:
            desc = "No change detected."
            bbox = None
            rel = None

        return [
            Evidence(
                id=str(uuid.uuid4()),
                tool="change_detection.bit",
                type=EvidenceType.MASK,
                payload={
                    "change_mask": mask,
                    "description": desc,
                    "bbox": bbox,
                    "relative_position": rel,
                    "source_image_a_id": image_a.id,
                    "source_image_b_id": image_b.id,
                },
                confidence=self.confidence,
                timing=0.01,
            )
        ]
