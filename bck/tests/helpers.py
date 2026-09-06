"""Reusable raster helpers for backend tests."""

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin


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
