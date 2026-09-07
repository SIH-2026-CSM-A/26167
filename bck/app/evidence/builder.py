"""Canonical evidence and answer assembly from verified VQA execution facts."""

from __future__ import annotations

import uuid

from rasterio import Affine
from rasterio.crs import CRS
from rasterio.errors import CRSError
from rasterio.warp import transform as warp_transform

from app.contracts import Answer, Evidence, EvidenceType, ExecutionTrace, ImageInput


def build_vqa_evidence(
    *,
    asset: ImageInput,
    model_id: str,
    raw_answer: str,
    verified_answer: str,
    supporting_observations: tuple[str, ...],
    rejected_claims: tuple[str, ...],
    timing_seconds: float,
) -> Evidence:
    """Create traceable text evidence without inventing unavailable confidence or geometry."""
    return Evidence(
        id=str(uuid.uuid4()),
        tool="internvl_vqa",
        type=EvidenceType.TEXT,
        payload={
            "source_asset_id": asset.id,
            "source_filename": asset.metadata.get("filename"),
            "source_format": asset.format,
            "source_metadata": dict(asset.metadata),
            "model_id": model_id,
            "raw_model_answer": raw_answer,
            "verified_answer": verified_answer,
            "supporting_observations": list(supporting_observations),
            "rejected_claims": list(rejected_claims),
            "confidence_available": False,
        },
        confidence=0.0,
        timing=timing_seconds,
    )


# Confidence tiers for bbox evidence, since neither InternVL's grounding output nor
# the Otsu fallback carries a calibrated confidence value. This module's own choice,
# not something specified in any project doc — same pattern as
# app.tools.fusion.reconcile's _SAR_ONLY_CONFIDENCE, flagged here for the same
# reason: an honest, disclosed tier beats a fabricated precise number, but it is
# still an authored guess. Native grounding is the model directly answering the
# grounding prompt (uncorroborated, like SAR alone); the Otsu fallback is a
# deterministic heuristic with no model judgment behind it at all, so it sits lower
# but still above RULE-VERIFY-02's confidence floor (0.30) so a real fallback bbox
# is not silently dropped.
_BBOX_NATIVE_CONFIDENCE = 0.75
_BBOX_OTSU_CONFIDENCE = 0.50


def _pixel_bbox_to_wgs84(
    bbox: list[int],
    *,
    visual_size: tuple[int, int],
    asset: ImageInput,
) -> list[float] | None:
    """Reproject a bbox from visual-preview pixel space to WGS84 [minLon, minLat, maxLon, maxLat].

    Returns None — never a fabricated or mislabeled coordinate — when the source asset
    has no usable CRS or transform to georeference against.

    Two corrections a naive pixel->geo conversion would miss:
    1. Scale: the pixel bbox comes from `source.visual`, ingestion's bounded model
       preview (bck/app/ingestion/raster.py's `_preview_dimensions`, capped at 1024px
       on the long side), which is not always the same size as the native raster the
       affine transform describes. Coordinates are rescaled into native pixel space
       first using the asset's own recorded width/height.
    2. All 4 corners: an affine with rotation/shear terms, or a reprojection that
       is not axis-aligned, can turn a rectangle into a quadrilateral — taking the
       min/max lon/lat across all 4 reprojected corners (not just 2) keeps the
       result a true bounding box instead of a skewed one.
    """
    crs_string = asset.metadata.get("crs")
    transform_coeffs = asset.metadata.get("transform")
    if not crs_string or not transform_coeffs:
        return None
    try:
        source_crs = CRS.from_string(str(crs_string))
    except CRSError:
        return None

    native_width = asset.metadata.get("width")
    native_height = asset.metadata.get("height")
    visual_width, visual_height = visual_size
    if not native_width or not native_height or visual_width <= 0 or visual_height <= 0:
        return None
    scale_x = native_width / visual_width
    scale_y = native_height / visual_height

    x1, y1, x2, y2 = bbox
    cols = (x1 * scale_x, x2 * scale_x, x2 * scale_x, x1 * scale_x)
    rows = (y1 * scale_y, y1 * scale_y, y2 * scale_y, y2 * scale_y)

    affine = Affine(*transform_coeffs)
    corners = [affine @ (col, row) for col, row in zip(cols, rows, strict=True)]
    native_xs, native_ys = zip(*corners, strict=True)

    lons, lats = warp_transform(source_crs, CRS.from_epsg(4326), list(native_xs), list(native_ys))
    return [min(lons), min(lats), max(lons), max(lats)]


def build_bbox_evidence(
    *,
    asset: ImageInput,
    model_id: str,
    bbox: list[int],
    visual_size: tuple[int, int],
    label: str,
    source: str,
    timing_seconds: float,
) -> Evidence | None:
    """Create traceable bbox evidence in WGS84, honestly labeled by which path produced it.

    Returns None when the source asset cannot be georeferenced — an ungeoreferenced
    pixel box is worse than no box, so raw pixel numbers are never shipped labeled as
    coordinates. The caller (pipeline.run) treats a None return the same as "neither
    grounding path produced a bbox": no BBOX evidence is added.
    """
    if source not in ("internvl_native", "otsu_fallback"):
        raise ValueError(f"unknown bbox source: {source!r}")

    wgs84_bbox = _pixel_bbox_to_wgs84(bbox, visual_size=visual_size, asset=asset)
    if wgs84_bbox is None:
        return None

    confidence = _BBOX_NATIVE_CONFIDENCE if source == "internvl_native" else _BBOX_OTSU_CONFIDENCE
    return Evidence(
        id=str(uuid.uuid4()),
        tool="internvl_vqa" if source == "internvl_native" else "otsu_fallback",
        type=EvidenceType.BBOX,
        payload={
            "source_asset_id": asset.id,
            "source_filename": asset.metadata.get("filename"),
            "bbox": wgs84_bbox,
            "pixel_bbox": list(bbox),
            "label": label,
            "source": source,
            "model_id": model_id if source == "internvl_native" else None,
        },
        confidence=confidence,
        timing=timing_seconds,
    )


def assemble_answer(
    *,
    text: str,
    evidence: list[Evidence],
    trace: ExecutionTrace,
    abstained: bool,
    abstention_reason: str | None,
) -> Answer:
    """Map verified text, canonical evidence, and trace into the existing response contract."""
    confidence = sum(item.confidence for item in evidence) / len(evidence) if evidence else 0.0
    return Answer(
        text=text,
        evidence=evidence,
        trace=trace,
        confidence=confidence,
        abstained=abstained,
        abstention_reason=abstention_reason,
    )
