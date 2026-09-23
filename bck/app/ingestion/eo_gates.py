"""Cross-raster EO validation gates run after ingestion and before routing.

Four metadata-only checks over a multi-raster request: CRS consistency, geographic
overlap, GSD match, and bi-temporal acquisition order. Each returns PASS, FAIL, or
NOT_COMPARABLE with a reason. A gate reports NOT_COMPARABLE, never FAIL, when the
metadata it needs is absent (e.g. PNG/JPEG uploads carry no CRS), so non-georeferenced
inputs keep their pre-existing behaviour. Turning a FAIL into a veto is the pipeline's
job; this module only evaluates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from rasterio.crs import CRS
from rasterio.errors import CRSError, RasterioError
from rasterio.warp import transform_bounds

from app.contracts import ImageInput

# Minimum intersection area as a fraction of the *smaller* footprint, so a small AOI
# fully inside a larger scene passes. 0.5 is this module's own authored choice (not
# specified in any project doc), flagged for review the same way
# app.tools.fusion.reconcile's _SAR_ONLY_CONFIDENCE is.
MIN_OVERLAP_FRACTION = 0.5

# Maximum ratio of coarser to finer pixel size on either axis. 1.5 is an authored
# choice (not from any project doc): it admits 10 m vs 10 m Sentinel-1/-2 pairs and
# small resampling differences, and rejects 10 m vs 20 m or 30 m pairs.
MAX_GSD_RATIO = 1.5

# TIFF 6.0 DateTime tag format. Per the TIFF spec this is the image *creation* time,
# which for many products is processing time rather than sensor acquisition time.
_TIFF_DATETIME_FORMAT = "%Y:%m:%d %H:%M:%S"


class EoGate(StrEnum):
    """Stable identifiers for the four cross-raster gates."""

    CRS_CONSISTENCY = "crs_consistency"
    GEOGRAPHIC_OVERLAP = "geographic_overlap"
    GSD_MATCH = "gsd_match"
    ACQUISITION_ORDER = "acquisition_order"


class EoGateStatus(StrEnum):
    """Gate outcome. Only FAIL may block a request."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_COMPARABLE = "NOT_COMPARABLE"


@dataclass(frozen=True, slots=True)
class EoGateResult:
    """One gate's outcome, reason, and the measured values behind it."""

    gate: EoGate
    status: EoGateStatus
    reason: str
    details: dict[str, object] = field(default_factory=dict)


def evaluate_eo_gates(sources: list[ImageInput]) -> list[EoGateResult]:
    """Run all four gates over a request with two or more rasters, in fixed order."""
    if len(sources) < 2:
        raise ValueError("EO gates compare rasters and need at least two")
    return [
        _crs_consistency(sources),
        _geographic_overlap(sources),
        _gsd_match(sources),
        _acquisition_order(sources),
    ]


def _parse_crs(source: ImageInput) -> CRS | None:
    """The raster's CRS, or None when absent or unparseable."""
    value = source.metadata.get("crs")
    if not isinstance(value, str) or not value:
        return None
    try:
        return CRS.from_string(value)
    except CRSError:
        return None


def _missing_crs_ids(sources: list[ImageInput]) -> list[str]:
    return [source.id for source in sources if _parse_crs(source) is None]


def _crs_consistency(sources: list[ImageInput]) -> EoGateResult:
    gate = EoGate.CRS_CONSISTENCY
    missing = _missing_crs_ids(sources)
    if missing:
        return EoGateResult(
            gate,
            EoGateStatus.NOT_COMPARABLE,
            "No readable CRS on one or more rasters (e.g. PNG/JPEG); CRS not compared.",
            {"missing_crs_ids": missing},
        )
    crs_by_id = {source.id: source.metadata["crs"] for source in sources}
    reference = _parse_crs(sources[0])
    if all(_parse_crs(source) == reference for source in sources[1:]):
        return EoGateResult(gate, EoGateStatus.PASS, "All rasters share one CRS.", crs_by_id)
    return EoGateResult(
        gate, EoGateStatus.FAIL, "Rasters are in different coordinate reference systems.", crs_by_id
    )


def _box_area(box: tuple[float, float, float, float]) -> float:
    left, bottom, right, top = box
    return max(0.0, right - left) * max(0.0, top - bottom)


def _geographic_overlap(sources: list[ImageInput]) -> EoGateResult:
    gate = EoGate.GEOGRAPHIC_OVERLAP
    missing = _missing_crs_ids(sources)
    if missing:
        return EoGateResult(
            gate,
            EoGateStatus.NOT_COMPARABLE,
            "No readable CRS on one or more rasters; bounds are pixel-space, not geographic.",
            {"missing_crs_ids": missing},
        )
    reference_crs = _parse_crs(sources[0])
    reference_box = tuple(sources[0].metadata["bounds"])
    fractions: dict[str, float] = {}
    for source in sources[1:]:
        box = tuple(source.metadata["bounds"])
        source_crs = _parse_crs(source)
        if source_crs != reference_crs:
            try:
                box = transform_bounds(source_crs, reference_crs, *box, densify_pts=21)
            except (RasterioError, ValueError) as error:
                return EoGateResult(
                    gate,
                    EoGateStatus.NOT_COMPARABLE,
                    f"Bounds of '{source.id}' could not be reprojected: {error}",
                )
        smaller_area = min(_box_area(reference_box), _box_area(box))
        if smaller_area <= 0.0 or not math.isfinite(smaller_area):
            return EoGateResult(
                gate,
                EoGateStatus.NOT_COMPARABLE,
                f"Raster '{source.id}' has a degenerate footprint; overlap not computed.",
            )
        intersection = (
            max(reference_box[0], box[0]),
            max(reference_box[1], box[1]),
            min(reference_box[2], box[2]),
            min(reference_box[3], box[3]),
        )
        fractions[source.id] = _box_area(intersection) / smaller_area

    worst = min(fractions.values())
    details = {
        "overlap_fraction_by_id": fractions,
        "min_overlap_fraction": MIN_OVERLAP_FRACTION,
        "reference_id": sources[0].id,
    }
    if worst < MIN_OVERLAP_FRACTION:
        return EoGateResult(
            gate,
            EoGateStatus.FAIL,
            f"Footprints overlap by {worst:.1%} of the smaller raster, "
            f"below the {MIN_OVERLAP_FRACTION:.0%} minimum.",
            details,
        )
    return EoGateResult(
        gate, EoGateStatus.PASS, f"Footprints overlap by at least {worst:.1%}.", details
    )


def _pixel_size(source: ImageInput) -> tuple[float, float]:
    """Absolute (x, y) pixel size from the affine, rotation-safe."""
    a, b, _c, d, e, _f = source.metadata["transform"]
    return math.hypot(a, d), math.hypot(b, e)


def _gsd_match(sources: list[ImageInput]) -> EoGateResult:
    gate = EoGate.GSD_MATCH
    missing = _missing_crs_ids(sources)
    if missing:
        return EoGateResult(
            gate,
            EoGateStatus.NOT_COMPARABLE,
            "No readable CRS on one or more rasters; pixel size has no ground unit.",
            {"missing_crs_ids": missing},
        )
    reference_crs = _parse_crs(sources[0])
    if any(_parse_crs(source) != reference_crs for source in sources[1:]):
        return EoGateResult(
            gate,
            EoGateStatus.NOT_COMPARABLE,
            "Rasters are in different CRSs; pixel sizes are in different units.",
        )
    sizes = {source.id: _pixel_size(source) for source in sources}
    if any(size <= 0.0 for pair in sizes.values() for size in pair):
        return EoGateResult(
            gate, EoGateStatus.NOT_COMPARABLE, "A raster reports a zero pixel size."
        )
    ratio = max(
        max(pair[axis] for pair in sizes.values()) / min(pair[axis] for pair in sizes.values())
        for axis in (0, 1)
    )
    details = {
        "pixel_size_by_id": {key: list(value) for key, value in sizes.items()},
        "gsd_ratio": ratio,
        "max_gsd_ratio": MAX_GSD_RATIO,
    }
    if ratio > MAX_GSD_RATIO:
        return EoGateResult(
            gate,
            EoGateStatus.FAIL,
            f"Pixel sizes differ by {ratio:.2f}x, above the {MAX_GSD_RATIO}x maximum.",
            details,
        )
    return EoGateResult(gate, EoGateStatus.PASS, f"Pixel sizes within {ratio:.2f}x.", details)


def _parse_datetime(source: ImageInput) -> datetime | None:
    value = source.metadata.get("acquisition_datetime")
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), _TIFF_DATETIME_FORMAT)
    except ValueError:
        return None


def _acquisition_order(sources: list[ImageInput]) -> EoGateResult:
    gate = EoGate.ACQUISITION_ORDER
    by_order = {source.metadata.get("capture_order"): source for source in sources}
    # Bi-temporal means two slot-ordered scenes of one modality. The Upload page also
    # sends slot order for an optical+SAR pair, which is cross-modal, not temporal.
    is_bitemporal = (
        len(sources) == 2 and set(by_order) == {0, 1} and sources[0].modality == sources[1].modality
    )
    if not is_bitemporal:
        return EoGateResult(gate, EoGateStatus.NOT_COMPARABLE, "Not a bi-temporal request.")
    before, after = by_order[0], by_order[1]
    t1, t2 = _parse_datetime(before), _parse_datetime(after)
    if t1 is None or t2 is None:
        return EoGateResult(
            gate,
            EoGateStatus.NOT_COMPARABLE,
            "Order declared by upload slot, not verified: no readable TIFFTAG_DATETIME "
            "on one or both rasters.",
        )
    details = {"t1": t1.isoformat(), "t2": t2.isoformat(), "source_tag": "TIFFTAG_DATETIME"}
    if t1 > t2:
        return EoGateResult(
            gate,
            EoGateStatus.FAIL,
            "The 'before' slot image is dated after the 'after' slot image.",
            details,
        )
    return EoGateResult(gate, EoGateStatus.PASS, "T1 is not later than T2.", details)
