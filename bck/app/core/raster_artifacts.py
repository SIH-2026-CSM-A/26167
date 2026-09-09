"""Shared host/container paths for derived raster artifacts."""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

from app.contracts import ImageInput
from app.core.tiles import get_cog_tile_url

REPO_ROOT = Path(__file__).resolve().parents[3]
HOST_RASTER_DIR = REPO_ROOT / "data" / "rasters"
CONTAINER_RASTER_DIR = "/data/rasters"


def ensure_raster_artifact_dir() -> Path:
    """Create and validate the shared derived-raster directory."""
    HOST_RASTER_DIR.mkdir(parents=True, exist_ok=True)
    if not HOST_RASTER_DIR.is_dir():
        raise OSError(f"Raster artifact path is not a directory: {HOST_RASTER_DIR}")
    return HOST_RASTER_DIR


def write_mask_artifact(mask: np.ndarray, source: ImageInput) -> str | None:
    """Write a georeferenced binary mask and return its container TiTiler URL."""
    metadata = source.metadata
    crs = metadata.get("crs")
    transform_values = metadata.get("transform")
    source_width = metadata.get("width")
    source_height = metadata.get("height")
    if (
        not isinstance(crs, str)
        or not crs.strip()
        or not _valid_transform(transform_values)
        or not isinstance(source_width, int)
        or not isinstance(source_height, int)
        or source_width <= 0
        or source_height <= 0
    ):
        return None
    output_dir = ensure_raster_artifact_dir()
    output_path = output_dir / f"{uuid.uuid4().hex}.tif"
    height, width = mask.shape
    transform = Affine(*transform_values) @ Affine.scale(
        source_width / width, source_height / height
    )
    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=1,
        dtype="uint8",
        crs=crs,
        transform=transform,
        compress="deflate",
        tiled=True,
    ) as dataset:
        dataset.write(mask.astype(np.uint8), 1)
    return get_cog_tile_url(f"{CONTAINER_RASTER_DIR}/{output_path.name}")


def _valid_transform(value: object) -> bool:
    """Validate affine transform coefficients from ingestion metadata."""
    return (
        isinstance(value, list)
        and len(value) == 6
        and all(isinstance(item, (int, float)) for item in value)
    )
