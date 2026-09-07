"""Canonical evidence construction tests."""

from pathlib import Path

import pytest
import rasterio
from rasterio import Affine
from rasterio.crs import CRS
from rasterio.warp import transform as warp_transform

from app.contracts import EvidenceType, ImageInput, Modality
from app.evidence import build_bbox_evidence, build_vqa_evidence

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
S2HAND_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"


def test_vqa_evidence_contains_actual_asset_and_model_provenance() -> None:
    """Text evidence must retain the source asset, filename, model, and real outputs."""
    asset = ImageInput(
        id="asset-1",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="scene.tif",
        metadata={"filename": "scene.tif", "width": 4, "height": 3},
    )

    evidence = build_vqa_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL2-2B",
        raw_answer="A river is visible.",
        verified_answer="A river is visible.",
        supporting_observations=("A river is visible.",),
        rejected_claims=(),
        timing_seconds=1.25,
    )

    assert evidence.type is EvidenceType.TEXT
    assert evidence.tool == "internvl_vqa"
    assert evidence.confidence == 0.0
    assert evidence.payload["confidence_available"] is False
    assert evidence.payload["source_asset_id"] == "asset-1"
    assert evidence.payload["source_filename"] == "scene.tif"
    assert evidence.payload["model_id"] == "OpenGVLab/InternVL2-2B"
    assert evidence.payload["raw_model_answer"] == "A river is visible."


def _asset(**metadata_overrides: object) -> ImageInput:
    metadata: dict[str, object] = {"filename": "scene.tif"}
    metadata.update(metadata_overrides)
    return ImageInput(
        id="asset-1",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="scene.tif",
        metadata=metadata,
    )


def _real_fixture_georeference() -> tuple[str, list[float], int, int]:
    """Read the real fixture's own crs/transform/width/height directly via rasterio."""
    if not S2HAND_PATH.exists():
        pytest.skip(f"real Sen1Floods11 S2Hand fixture not present at {S2HAND_PATH}")
    with rasterio.open(S2HAND_PATH) as src:
        crs = src.crs.to_string()
        transform_coeffs = [
            src.transform.a,
            src.transform.b,
            src.transform.c,
            src.transform.d,
            src.transform.e,
            src.transform.f,
        ]
        return crs, transform_coeffs, src.width, src.height


def _real_fixture_wgs84_bounds() -> tuple[float, float, float, float]:
    """The real fixture raster's own full-extent bounds, reprojected to WGS84 independently."""
    with rasterio.open(S2HAND_PATH) as src:
        crs = src.crs
        bounds = src.bounds
    lons, lats = warp_transform(
        crs, CRS.from_epsg(4326), [bounds.left, bounds.right], [bounds.bottom, bounds.top]
    )
    return min(lons), min(lats), max(lons), max(lats)


def test_bbox_evidence_native_source_reprojects_to_wgs84_within_real_raster_bounds() -> None:
    """The emitted bbox must be real WGS84 coordinates, not raw pixel numbers relabeled."""
    crs, transform_coeffs, width, height = _real_fixture_georeference()
    asset = _asset(crs=crs, transform=transform_coeffs, width=width, height=height)
    pixel_bbox = [100, 200, 300, 400]

    evidence = build_bbox_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL3-2B",
        bbox=pixel_bbox,
        visual_size=(width, height),
        label="flooded area",
        source="internvl_native",
        timing_seconds=0.8,
    )

    assert evidence is not None
    assert evidence.type is EvidenceType.BBOX
    assert evidence.tool == "internvl_vqa"
    assert evidence.payload["label"] == "flooded area"
    assert evidence.payload["source"] == "internvl_native"
    assert evidence.payload["model_id"] == "OpenGVLab/InternVL3-2B"
    assert evidence.payload["source_asset_id"] == "asset-1"
    assert evidence.confidence == 0.75

    # The raw pixel box is retained for audit, but never shipped as "bbox" itself.
    assert evidence.payload["pixel_bbox"] == pixel_bbox
    assert evidence.payload["bbox"] != pixel_bbox

    min_lon, min_lat, max_lon, max_lat = evidence.payload["bbox"]
    raster_min_lon, raster_min_lat, raster_max_lon, raster_max_lat = _real_fixture_wgs84_bounds()
    assert raster_min_lon <= min_lon <= max_lon <= raster_max_lon
    assert raster_min_lat <= min_lat <= max_lat <= raster_max_lat


def test_bbox_evidence_otsu_fallback_is_not_presented_as_model_output() -> None:
    """A heuristic fallback box must never be reported under the model's identity."""
    crs, transform_coeffs, width, height = _real_fixture_georeference()
    asset = _asset(crs=crs, transform=transform_coeffs, width=width, height=height)

    evidence = build_bbox_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL3-2B",
        bbox=[0, 0, 385, 512],
        visual_size=(width, height),
        label="flooded area",
        source="otsu_fallback",
        timing_seconds=0.3,
    )

    assert evidence is not None
    assert evidence.tool == "otsu_fallback"
    assert evidence.payload["source"] == "otsu_fallback"
    assert evidence.payload["model_id"] is None
    assert evidence.confidence == 0.50
    assert evidence.confidence < 0.75  # strictly less trusted than a native box


def test_bbox_evidence_rescales_a_downscaled_preview_to_native_pixel_space() -> None:
    """A bbox computed on a smaller model preview must not be applied to the affine unscaled.

    Ingestion bounds previews to 1024px on the long side (raster.py's
    `_preview_dimensions`), so a native raster larger than that produces a `visual`
    image smaller than the dataset the transform describes. Simulates that gap
    directly against the real fixture's own affine, independently re-deriving the
    expected result rather than re-running the function under test on itself.
    """
    crs, transform_coeffs, native_width, native_height = _real_fixture_georeference()
    # Emulate a 2x-downscaled preview of an otherwise-identical raster.
    visual_size = (native_width // 2, native_height // 2)
    asset = _asset(crs=crs, transform=transform_coeffs, width=native_width, height=native_height)
    pixel_bbox = [100, 200, 300, 400]  # in the downscaled visual's pixel space

    evidence = build_bbox_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL3-2B",
        bbox=pixel_bbox,
        visual_size=visual_size,
        label="flooded area",
        source="internvl_native",
        timing_seconds=0.8,
    )
    assert evidence is not None

    scale_x = native_width / visual_size[0]
    scale_y = native_height / visual_size[1]
    x1, y1, x2, y2 = pixel_bbox
    cols = (x1 * scale_x, x2 * scale_x, x2 * scale_x, x1 * scale_x)
    rows = (y1 * scale_y, y1 * scale_y, y2 * scale_y, y2 * scale_y)
    affine = Affine(*transform_coeffs)
    corners = [affine @ (col, row) for col, row in zip(cols, rows, strict=True)]
    xs, ys = zip(*corners, strict=True)
    expected_lons, expected_lats = warp_transform(
        CRS.from_string(crs), CRS.from_epsg(4326), list(xs), list(ys)
    )
    expected_bbox = [min(expected_lons), min(expected_lats), max(expected_lons), max(expected_lats)]

    assert evidence.payload["bbox"] == pytest.approx(expected_bbox)


def test_bbox_evidence_abstains_without_a_crs() -> None:
    """An ungeoreferenced asset must never emit a pixel box mislabeled as coordinates."""
    asset = _asset(crs=None, transform=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0], width=512, height=512)

    evidence = build_bbox_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL3-2B",
        bbox=[100, 200, 300, 400],
        visual_size=(512, 512),
        label="flooded area",
        source="internvl_native",
        timing_seconds=0.8,
    )

    assert evidence is None


def test_bbox_evidence_abstains_on_unparseable_crs() -> None:
    asset = _asset(
        crs="not-a-real-crs", transform=[1.0, 0.0, 0.0, 0.0, 1.0, 0.0], width=512, height=512
    )

    evidence = build_bbox_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL3-2B",
        bbox=[100, 200, 300, 400],
        visual_size=(512, 512),
        label="flooded area",
        source="internvl_native",
        timing_seconds=0.8,
    )

    assert evidence is None


def test_bbox_evidence_rejects_unknown_source() -> None:
    crs, transform_coeffs, width, height = _real_fixture_georeference()
    asset = _asset(crs=crs, transform=transform_coeffs, width=width, height=height)
    with pytest.raises(ValueError):
        build_bbox_evidence(
            asset=asset,
            model_id="OpenGVLab/InternVL3-2B",
            bbox=[0, 0, 10, 10],
            visual_size=(width, height),
            label="x",
            source="made_up",
            timing_seconds=0.1,
        )
