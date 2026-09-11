"""B4: metadata-only modality classification and the client-override boundary.

Uses the real Sentinel-1/Sentinel-2 Bolivia_103757 fixtures (same ones B1's
fusion fix targets) as the real SAR and Optical cases, since their band
descriptions are real satellite product metadata ("VV"/"VH" and
"B1".."B8A".."B12" respectively) — not synthesized for this test.
"""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.io import MemoryFile

from app.contracts import Modality
from app.ingestion import RasterUpload, classify_modality, ingest_raster
from tests.helpers import make_geotiff_bytes

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
S2_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"


def _make_ambiguous_geotiff_bytes() -> bytes:
    """A structurally valid GeoTIFF with no band descriptions, tags, or RGB colorinterp.

    Unlike tests.helpers.make_geotiff_bytes (which declares Red/Green/Blue
    colorinterp on purpose), this is genuinely unclassifiable from metadata —
    the actual case B4 exists to catch, not a strawman.
    """
    array = np.zeros((2, 3, 4), dtype=np.uint8)
    with MemoryFile() as memory_file:
        with memory_file.open(driver="GTiff", width=4, height=3, count=2, dtype="uint8") as dataset:
            dataset.write(array)
        return memory_file.read()


def test_classify_modality_real_sentinel1_grd_band_descriptions_is_sar():
    if not S1_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present under {FIXTURES_DIR}")
    with rasterio.open(S1_PATH) as dataset:
        assert dataset.descriptions == ("VV", "VH")  # real product metadata, not assumed
        assert classify_modality(dataset) == Modality.SAR


def test_classify_modality_real_sentinel2_band_descriptions_is_optical():
    if not S2_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present under {FIXTURES_DIR}")
    with rasterio.open(S2_PATH) as dataset:
        assert dataset.descriptions[0] == "B1"  # real product metadata, not assumed
        assert classify_modality(dataset) == Modality.OPTICAL


def test_classify_modality_stripped_metadata_is_unknown():
    with MemoryFile(_make_ambiguous_geotiff_bytes()) as memory_file, memory_file.open() as dataset:
        assert dataset.descriptions == (None, None)
        assert classify_modality(dataset) == Modality.UNKNOWN


def test_classify_modality_natural_rgb_colorinterp_is_optical():
    """A natural-color raster with no band names still classifies via colorinterp."""
    with MemoryFile(make_geotiff_bytes()) as memory_file, memory_file.open() as dataset:
        assert classify_modality(dataset) == Modality.OPTICAL


def test_ingest_raster_classifies_when_modality_omitted():
    if not S1_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present under {FIXTURES_DIR}")
    upload = RasterUpload(
        id="sar-1",
        filename="Bolivia_103757_S1Hand.tif",
        content_type="image/tiff",
        content=S1_PATH.read_bytes(),
        modality=None,
    )
    ingested = ingest_raster(upload)
    assert ingested.source.modality == Modality.SAR
    assert ingested.source.metadata["modality_source"] == "metadata_classifier"


def test_ingest_raster_unknown_modality_still_ingests_as_unknown():
    upload = RasterUpload(
        id="ambiguous-1",
        filename="ambiguous.tif",
        content_type="image/tiff",
        content=_make_ambiguous_geotiff_bytes(),
        modality=None,
    )
    ingested = ingest_raster(upload)
    assert ingested.source.modality == Modality.UNKNOWN
    assert ingested.source.metadata["modality_source"] == "metadata_classifier"


def test_ingest_raster_client_override_bypasses_classification():
    """An explicit client-supplied modality is used as-is, not re-classified."""
    upload = RasterUpload(
        id="override-1",
        filename="ambiguous.tif",
        content_type="image/tiff",
        content=_make_ambiguous_geotiff_bytes(),
        modality=Modality.SAR,
    )
    ingested = ingest_raster(upload)
    assert ingested.source.modality == Modality.SAR
    assert ingested.source.metadata["modality_source"] == "client_override"
