"""GeoTIFF ingestion behavior tests."""

import numpy as np
import pytest

from app.contracts import Modality
from app.ingestion import InvalidRasterError, RasterUpload, UnsupportedRasterError, ingest_raster
from app.ingestion.raster import _normalize_band
from tests.helpers import make_geotiff_bytes


def _upload(filename: str, content: bytes) -> RasterUpload:
    """Build a raster upload with stable test identity."""
    return RasterUpload(
        id="asset-1",
        filename=filename,
        content_type="image/tiff",
        content=content,
        modality=Modality.OPTICAL,
    )


def test_ingest_geotiff_extracts_metadata_and_model_ready_visual() -> None:
    """A readable GeoTIFF must retain source metadata and produce an RGB visual."""
    ingested = ingest_raster(_upload("scene.tiff", make_geotiff_bytes()))

    assert ingested.source.id == "asset-1"
    assert ingested.source.format == "GTiff"
    assert ingested.source.metadata["width"] == 4
    assert ingested.source.metadata["height"] == 3
    assert ingested.source.metadata["band_count"] == 3
    assert ingested.source.metadata["dtype"] == "uint8"
    assert ingested.source.metadata["crs"] == "EPSG:4326"
    assert ingested.source.metadata["nodata"] == 0.0
    assert ingested.source.metadata["filename"] == "scene.tiff"
    assert len(ingested.source.metadata["bounds"]) == 4
    assert len(ingested.source.metadata["transform"]) == 6
    assert ingested.visual.mode == "RGB"
    assert ingested.visual.size == (4, 3)


def test_ingest_rejects_unsupported_extension() -> None:
    """A non-TIFF extension must fail before raster decoding."""
    with pytest.raises(UnsupportedRasterError, match=".tif or .tiff"):
        ingest_raster(_upload("scene.png", make_geotiff_bytes()))


def test_ingest_rejects_unreadable_tiff() -> None:
    """Invalid TIFF bytes must become a typed ingestion error rather than a crash."""
    with pytest.raises(InvalidRasterError, match="could not be read"):
        ingest_raster(_upload("broken.tif", b"not-a-raster"))


def test_normalize_band_handles_int16_masked_array() -> None:
    """Integer masked arrays must cast to float before filling NaN to prevent TypeError."""
    data = np.array([[100, 200], [300, 400]], dtype=np.int16)
    mask = np.array([[False, False], [False, True]])
    band = np.ma.MaskedArray(data, mask=mask)

    normalized = _normalize_band(band)

    assert normalized.dtype == np.uint8
    assert normalized.shape == (2, 2)
    assert normalized[1, 1] == 0
    assert normalized[0, 0] <= normalized[0, 1] <= normalized[1, 0]
