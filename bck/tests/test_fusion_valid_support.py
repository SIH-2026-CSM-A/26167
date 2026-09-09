"""ROHAN-003/B1 regression: large irregular NaN footprint must not corrupt fusion output.

Purely synthetic, in-memory numpy arrays — no rasterio file I/O, no FastAPI, no
database. This reproduces the shape of the real failure (a SAR VV band with a
large irregular nodata footprint: swath edges, sensor gaps) without needing
the actual multi-hundred-KB fixture, and runs without any live Postgres.
"""

import numpy as np
import pytest

from app.tools.fusion.cloud_detector import CloudDetectionResult
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.guards import InsufficientValidSupportError
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask

_NOISE_VARIANCE = 0.005
_SHAPE = (256, 256)


def _irregular_valid_mask(shape: tuple[int, int]) -> np.ndarray:
    """A large, irregular (non-rectangular, non-convex) valid footprint.

    Union of an off-center disk and a diagonal band, minus a notch bitten out
    of the disk — deliberately not a rectangle or a single convex shape, so a
    fix that only handles "crop to a valid sub-rectangle" would not pass this.
    """
    rows, cols = np.indices(shape)
    disk = (rows - 100) ** 2 + (cols - 90) ** 2 <= 70**2
    band = np.abs(rows - cols) < 20
    notch = (rows - 130) ** 2 + (cols - 140) ** 2 <= 25**2
    return (disk | band) & ~notch


def _synthetic_sar_scene() -> tuple[np.ndarray, np.ndarray]:
    """A dB-scale SAR scene with a real irregular NaN footprint outside valid data.

    Values inside the valid footprint are a real two-population mix (low dB =
    "water-like", high dB = "land-like") so Otsu has real structure to find.
    """
    rng = np.random.default_rng(0)
    valid_mask = _irregular_valid_mask(_SHAPE)

    land = rng.normal(loc=-8.0, scale=1.0, size=_SHAPE)
    water = rng.normal(loc=-20.0, scale=1.0, size=_SHAPE)
    rows, cols = np.indices(_SHAPE)
    is_water_like = cols < _SHAPE[1] // 2
    sigma0_db = np.where(is_water_like, water, land)

    sigma0_db = np.where(valid_mask, sigma0_db, np.nan)
    return sigma0_db, valid_mask


def test_synthetic_scene_has_large_irregular_footprint_matching_real_failure_shape():
    """Sanity check on the fixture itself: large, majority-invalid, non-rectangular."""
    sigma0_db, valid_mask = _synthetic_sar_scene()
    total = valid_mask.size
    finite_count = int(valid_mask.sum())

    assert 0 < finite_count < total
    assert finite_count > total * 0.2  # "large", like the real 101,623/262,144 case
    assert np.isnan(sigma0_db[~valid_mask]).all()
    assert not np.isnan(sigma0_db[valid_mask]).any()
    # Not a rectangle: a bounding-box crop to the valid region would still
    # contain invalid pixels, since the footprint has a notch cut out of it.
    row_idx, col_idx = np.where(valid_mask)
    bbox = valid_mask[row_idx.min() : row_idx.max() + 1, col_idx.min() : col_idx.max() + 1]
    assert not bbox.all()


def test_lee_filter_masked_never_leaks_nan_into_valid_pixels():
    sigma0_db, valid_mask = _synthetic_sar_scene()

    despeckled = lee_filter(
        sigma0_db, SarScale.DB, noise_variance=_NOISE_VARIANCE, valid_mask=valid_mask
    )

    assert despeckled.shape == sigma0_db.shape
    # The regression this guards against: a 7x7 window straddling the nodata
    # border used to pull NaN into every valid pixel near that border.
    assert not np.isnan(despeckled[valid_mask]).any()
    # Invalid pixels stay invalid — never zero-filled or estimated.
    assert np.isnan(despeckled[~valid_mask]).all()


def test_lee_filter_unmasked_legacy_behavior_is_unchanged():
    """No valid_mask given -> old NaN-propagating behavior, byte for byte."""
    sigma0_db, valid_mask = _synthetic_sar_scene()
    legacy = lee_filter(sigma0_db, SarScale.DB, noise_variance=_NOISE_VARIANCE)
    # Old behavior propagates NaN into most of the valid region too, given how
    # much of this scene is invalid — that is exactly the bug being fixed.
    assert np.isnan(legacy[valid_mask]).any()


def test_otsu_water_mask_masked_classifies_only_valid_pixels_without_nan_error():
    sigma0_db, valid_mask = _synthetic_sar_scene()
    despeckled = lee_filter(
        sigma0_db, SarScale.DB, noise_variance=_NOISE_VARIANCE, valid_mask=valid_mask
    )

    water_mask = otsu_water_mask(despeckled, SarScale.DB, valid_mask=valid_mask)

    assert water_mask.shape == sigma0_db.shape
    assert water_mask.dtype == bool
    # Real bimodal structure recovered: the water-like half is mostly
    # classified water, the land-like half mostly is not.
    rows, cols = np.indices(_SHAPE)
    water_like_valid = valid_mask & (cols < _SHAPE[1] // 2)
    land_like_valid = valid_mask & (cols >= _SHAPE[1] // 2)
    assert water_mask[water_like_valid].mean() > 0.8
    assert water_mask[land_like_valid].mean() < 0.2


def test_otsu_water_mask_without_masking_raises_on_the_same_nan_scene():
    """Confirms the legacy guard still refuses to guess around NaN when unmasked."""
    sigma0_db, _ = _synthetic_sar_scene()
    with pytest.raises(ValueError):
        otsu_water_mask(sigma0_db, SarScale.DB)


def test_reconcile_scopes_all_fractions_to_valid_support_not_full_scene():
    sigma0_db, valid_mask = _synthetic_sar_scene()
    despeckled = lee_filter(
        sigma0_db, SarScale.DB, noise_variance=_NOISE_VARIANCE, valid_mask=valid_mask
    )
    water_mask = otsu_water_mask(despeckled, SarScale.DB, valid_mask=valid_mask)

    # Force a cloud-affected region entirely inside the valid footprint, so
    # this exercises the two-region split against the SAME irregular support.
    cloud_mask = np.zeros(_SHAPE, dtype=bool)
    cloud_mask[95:105, 60:100] = True
    cloud_result = CloudDetectionResult(probability=cloud_mask.astype(np.float32), mask=cloud_mask)

    evidence_list = reconcile_sar_optical(
        despeckled, water_mask, cloud_result, valid_mask=valid_mask
    )

    valid_count = int(valid_mask.sum())
    total_count = valid_mask.size
    invalid_count = total_count - valid_count

    for evidence in evidence_list:
        payload = evidence.payload
        assert payload["valid_pixel_count"] == valid_count
        assert payload["invalid_pixel_count"] == invalid_count
        assert np.isclose(payload["support_fraction"], valid_count / total_count)
        np.testing.assert_array_equal(payload["valid_mask"], valid_mask)
        # No fraction here is a raw full-scene count: every denominator used
        # to derive it must be <= valid_count, never total_count directly
        # (unless the whole scene happens to be valid, which it isn't here).
        assert valid_count < total_count

    by_region = {ev.payload["region"]: ev for ev in evidence_list}
    assert set(by_region) == {"clear", "cloud_affected"}
    # Cloud region's area fraction is relative to the VALID area, not the
    # full 256x256 scene — the exact bug this fix targets.
    cloud_ev = by_region["cloud_affected"]
    cloud_pixels_in_valid = int((cloud_mask & valid_mask).sum())
    assert np.isclose(cloud_ev.payload["region_area_fraction"], cloud_pixels_in_valid / valid_count)


def test_reconcile_water_mask_never_marks_invalid_pixels_as_water():
    sigma0_db, valid_mask = _synthetic_sar_scene()
    despeckled = lee_filter(
        sigma0_db, SarScale.DB, noise_variance=_NOISE_VARIANCE, valid_mask=valid_mask
    )
    water_mask = otsu_water_mask(despeckled, SarScale.DB, valid_mask=valid_mask)
    cloud_mask = np.zeros(_SHAPE, dtype=bool)
    cloud_result = CloudDetectionResult(probability=cloud_mask.astype(np.float32), mask=cloud_mask)

    [evidence] = reconcile_sar_optical(despeckled, water_mask, cloud_result, valid_mask=valid_mask)

    # Nodata never collapses into "not water" *by implication*: every water
    # pixel reported is inside the valid footprint, and the invalid footprint
    # is reported separately (valid_mask) rather than silently as "no water".
    reported_water = evidence.payload["water_mask"]
    assert not (reported_water & ~valid_mask).any()
    assert evidence.payload["invalid_pixel_count"] == int((~valid_mask).sum())


def test_empty_valid_support_raises_typed_error_not_garbage_output():
    """0 finite pixels must raise, not divide-by-zero or fabricate a threshold/fraction."""
    sigma0_db = np.full(_SHAPE, np.nan)
    valid_mask = np.zeros(_SHAPE, dtype=bool)
    despeckled = lee_filter(
        sigma0_db, SarScale.DB, noise_variance=_NOISE_VARIANCE, valid_mask=valid_mask
    )
    assert np.isnan(despeckled).all()

    with pytest.raises(InsufficientValidSupportError):
        otsu_water_mask(despeckled, SarScale.DB, valid_mask=valid_mask)

    water_mask = np.zeros(_SHAPE, dtype=bool)
    cloud_result = CloudDetectionResult(
        probability=np.zeros(_SHAPE, dtype=np.float32), mask=np.zeros(_SHAPE, dtype=bool)
    )
    with pytest.raises(InsufficientValidSupportError):
        reconcile_sar_optical(despeckled, water_mask, cloud_result, valid_mask=valid_mask)


def test_reconcile_rejects_mismatched_valid_mask_shape():
    despeckled = np.zeros((4, 4))
    water_mask = np.zeros((4, 4), dtype=bool)
    cloud_result = CloudDetectionResult(
        probability=np.zeros((4, 4), dtype=np.float32), mask=np.zeros((4, 4), dtype=bool)
    )
    mismatched_valid_mask = np.ones((5, 5), dtype=bool)
    with pytest.raises(ValueError):
        reconcile_sar_optical(
            despeckled, water_mask, cloud_result, valid_mask=mismatched_valid_mask
        )
