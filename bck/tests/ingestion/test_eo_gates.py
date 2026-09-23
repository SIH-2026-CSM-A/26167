"""Cross-raster EO validation gates over synthetic in-memory GeoTIFFs and real fixtures."""

from pathlib import Path

import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds, from_origin
from rasterio.warp import transform_bounds

from app.contracts import ImageInput, Modality
from app.ingestion import (
    EoGate,
    EoGateStatus,
    RasterUpload,
    evaluate_eo_gates,
    ingest_raster,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"

# 4x4 pixels at 0.01 deg from (77.0 E, 13.0 N): the same origin tests/helpers.py uses.
_ORIGIN_4326 = from_origin(77.0, 13.0, 0.01, 0.01)
_BOUNDS_4326 = (77.0, 12.96, 77.04, 13.0)


def _geotiff(
    *,
    crs: str | None = "EPSG:4326",
    transform=_ORIGIN_4326,
    size: int = 4,
    datetime_tag: str | None = None,
) -> bytes:
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            width=size,
            height=size,
            count=1,
            dtype="uint8",
            crs=crs,
            transform=transform,
        ) as dataset:
            dataset.write(np.full((1, size, size), 7, dtype=np.uint8))
            if datetime_tag is not None:
                dataset.update_tags(TIFFTAG_DATETIME=datetime_tag)
        return memory_file.read()


def _source(asset_id: str, content: bytes, capture_order: int | None = None) -> ImageInput:
    return ingest_raster(
        RasterUpload(
            id=asset_id,
            filename=f"{asset_id}.tif",
            content_type="image/tiff",
            content=content,
            modality=Modality.OPTICAL,
            capture_order=capture_order,
        )
    ).source


def _gate(sources: list[ImageInput], gate: EoGate):
    return next(result for result in evaluate_eo_gates(sources) if result.gate == gate)


def _utm_twin() -> bytes:
    """Same footprint as the default raster, expressed in UTM zone 43N."""
    utm_bounds = transform_bounds("EPSG:4326", "EPSG:32643", *_BOUNDS_4326)
    return _geotiff(crs="EPSG:32643", transform=from_bounds(*utm_bounds, 4, 4))


def test_requires_two_rasters() -> None:
    with pytest.raises(ValueError, match="at least two"):
        evaluate_eo_gates([_source("a", _geotiff())])


def test_datetime_tag_round_trips_through_ingestion() -> None:
    source = _source("a", _geotiff(datetime_tag="2024:03:01 10:00:00"))
    assert source.metadata["acquisition_datetime"] == "2024:03:01 10:00:00"


# --- 1. CRS consistency -------------------------------------------------------


def test_crs_pass_when_identical() -> None:
    sources = [_source("a", _geotiff()), _source("b", _geotiff())]
    assert _gate(sources, EoGate.CRS_CONSISTENCY).status == EoGateStatus.PASS


def test_crs_fail_when_different() -> None:
    sources = [_source("a", _geotiff()), _source("b", _utm_twin())]
    result = _gate(sources, EoGate.CRS_CONSISTENCY)
    assert result.status == EoGateStatus.FAIL
    assert result.details == {"a": "EPSG:4326", "b": "EPSG:32643"}


def test_crs_not_comparable_when_missing() -> None:
    sources = [_source("a", _geotiff()), _source("b", _geotiff(crs=None))]
    result = _gate(sources, EoGate.CRS_CONSISTENCY)
    assert result.status == EoGateStatus.NOT_COMPARABLE
    assert result.details["missing_crs_ids"] == ["b"]


# --- 2. Geographic overlap ----------------------------------------------------


def test_overlap_pass_when_identical_footprint() -> None:
    sources = [_source("a", _geotiff()), _source("b", _geotiff())]
    result = _gate(sources, EoGate.GEOGRAPHIC_OVERLAP)
    assert result.status == EoGateStatus.PASS
    assert result.details["overlap_fraction_by_id"]["b"] == pytest.approx(1.0)


def test_overlap_pass_after_reprojecting_different_crs() -> None:
    sources = [_source("a", _geotiff()), _source("b", _utm_twin())]
    result = _gate(sources, EoGate.GEOGRAPHIC_OVERLAP)
    assert result.status == EoGateStatus.PASS
    assert result.details["overlap_fraction_by_id"]["b"] > 0.95


def test_overlap_fail_when_footprints_barely_touch() -> None:
    # Shifted 3 of 4 pixels east: 25% overlap, below the 50% minimum.
    shifted = _geotiff(transform=from_origin(77.03, 13.0, 0.01, 0.01))
    sources = [_source("a", _geotiff()), _source("b", shifted)]
    result = _gate(sources, EoGate.GEOGRAPHIC_OVERLAP)
    assert result.status == EoGateStatus.FAIL
    assert result.details["overlap_fraction_by_id"]["b"] == pytest.approx(0.25)


def test_overlap_not_comparable_when_crs_missing() -> None:
    sources = [_source("a", _geotiff(crs=None)), _source("b", _geotiff(crs=None))]
    assert _gate(sources, EoGate.GEOGRAPHIC_OVERLAP).status == EoGateStatus.NOT_COMPARABLE


# --- 3. GSD match -------------------------------------------------------------


def test_gsd_pass_when_equal() -> None:
    sources = [_source("a", _geotiff()), _source("b", _geotiff())]
    result = _gate(sources, EoGate.GSD_MATCH)
    assert result.status == EoGateStatus.PASS
    assert result.details["gsd_ratio"] == pytest.approx(1.0)


def test_gsd_fail_when_three_times_coarser() -> None:
    coarse = _geotiff(transform=from_origin(77.0, 13.0, 0.03, 0.03))
    sources = [_source("a", _geotiff()), _source("b", coarse)]
    result = _gate(sources, EoGate.GSD_MATCH)
    assert result.status == EoGateStatus.FAIL
    assert result.details["gsd_ratio"] == pytest.approx(3.0)


def test_gsd_not_comparable_when_crs_missing() -> None:
    sources = [_source("a", _geotiff()), _source("b", _geotiff(crs=None))]
    assert _gate(sources, EoGate.GSD_MATCH).status == EoGateStatus.NOT_COMPARABLE


def test_gsd_not_comparable_across_crs_units() -> None:
    sources = [_source("a", _geotiff()), _source("b", _utm_twin())]
    assert _gate(sources, EoGate.GSD_MATCH).status == EoGateStatus.NOT_COMPARABLE


# --- 4. Acquisition order -----------------------------------------------------


def _pair(t1: str | None, t2: str | None) -> list[ImageInput]:
    return [
        _source("before", _geotiff(datetime_tag=t1), capture_order=0),
        _source("after", _geotiff(datetime_tag=t2), capture_order=1),
    ]


def test_order_pass_when_t1_before_t2() -> None:
    result = _gate(_pair("2023:01:01 00:00:00", "2024:01:01 00:00:00"), EoGate.ACQUISITION_ORDER)
    assert result.status == EoGateStatus.PASS


def test_order_fail_when_t1_after_t2() -> None:
    result = _gate(_pair("2024:01:01 00:00:00", "2023:01:01 00:00:00"), EoGate.ACQUISITION_ORDER)
    assert result.status == EoGateStatus.FAIL
    assert result.details["t1"] == "2024-01-01T00:00:00"


def test_order_not_comparable_without_dates_keeps_slot_order() -> None:
    result = _gate(_pair(None, "2024:01:01 00:00:00"), EoGate.ACQUISITION_ORDER)
    assert result.status == EoGateStatus.NOT_COMPARABLE
    assert "order declared by upload slot, not verified" in result.reason.lower()


def test_order_not_comparable_without_capture_order() -> None:
    sources = [_source("a", _geotiff()), _source("b", _geotiff())]
    result = _gate(sources, EoGate.ACQUISITION_ORDER)
    assert result.status == EoGateStatus.NOT_COMPARABLE
    assert result.reason == "Not a bi-temporal request."


def test_order_skipped_for_cross_modal_pair_even_with_slot_order() -> None:
    # The Upload page sends capture_order 0/1 for its optical+SAR slots too; dated
    # reversed here to prove the gate is skipped, not evaluated.
    optical = _source("optical", _geotiff(datetime_tag="2024:01:01 00:00:00"), capture_order=0)
    sar = ingest_raster(
        RasterUpload(
            id="sar",
            filename="sar.tif",
            content_type="image/tiff",
            content=_geotiff(datetime_tag="2023:01:01 00:00:00"),
            modality=Modality.SAR,
            capture_order=1,
        )
    ).source
    result = _gate([optical, sar], EoGate.ACQUISITION_ORDER)
    assert result.status == EoGateStatus.NOT_COMPARABLE
    assert result.reason == "Not a bi-temporal request."


# --- Real fixture pairs -------------------------------------------------------


def _fixture_source(name: str, capture_order: int | None = None) -> ImageInput:
    path = FIXTURES_DIR / name
    if not path.exists():
        pytest.skip(f"fixture {name} not present under {FIXTURES_DIR}")
    return ingest_raster(
        RasterUpload(
            id=name,
            filename=name,
            content_type="image/tiff" if name.endswith(".tif") else "image/png",
            content=path.read_bytes(),
            modality=None,
            capture_order=capture_order,
        )
    ).source


def test_sen1floods11_pair_passes_spatial_gates() -> None:
    sources = [
        _fixture_source("Bolivia_103757_S2Hand.tif"),
        _fixture_source("Bolivia_103757_S1Hand.tif"),
    ]
    statuses = {result.gate: result.status for result in evaluate_eo_gates(sources)}
    assert statuses == {
        EoGate.CRS_CONSISTENCY: EoGateStatus.PASS,
        EoGate.GEOGRAPHIC_OVERLAP: EoGateStatus.PASS,
        EoGate.GSD_MATCH: EoGateStatus.PASS,
        EoGate.ACQUISITION_ORDER: EoGateStatus.NOT_COMPARABLE,
    }


def test_levir_png_pair_is_never_blocked() -> None:
    sources = [
        _fixture_source("levir_test_1_t1.png", capture_order=0),
        _fixture_source("levir_test_1_t2.png", capture_order=1),
    ]
    assert all(
        result.status == EoGateStatus.NOT_COMPARABLE for result in evaluate_eo_gates(sources)
    )
