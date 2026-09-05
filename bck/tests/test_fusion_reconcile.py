from pathlib import Path

import numpy as np
import pytest
import rasterio

from app.tools.fusion.cloud_detector import CloudDetectionResult, detect_clouds
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
S2_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"
_NOISE_VARIANCE = 0.005


def _load_crop(row0: int, col0: int, size: int):
    with rasterio.open(S1_PATH) as src:
        vv = src.read(1)[row0 : row0 + size, col0 : col0 + size].astype(np.float64)
    with rasterio.open(S2_PATH) as src:
        s2 = src.read()[:, row0 : row0 + size, col0 : col0 + size]
    return vv, s2


def _run_pipeline(vv: np.ndarray, s2: np.ndarray):
    despeckled = lee_filter(vv, SarScale.DB, noise_variance=_NOISE_VARIANCE)
    water = otsu_water_mask(despeckled, SarScale.DB)
    reflectance = np.moveaxis(s2, 0, -1).astype(np.float32) / 10000.0
    cloud_result = detect_clouds(reflectance)
    return despeckled, water, cloud_result


@pytest.fixture
def clean_region():
    # 128x128 block at row 80, col 368 of the real Bolivia_103757 chip.
    # Verified by scanning the full 512x512 scene for a region with zero
    # cloud-detector-flagged pixels AND a NaN-free SAR VV band — this is a
    # genuinely 0%-cloud real sub-region, not assumed from the whole scene's
    # low overall cloud fraction (which is NOT exactly zero — see below).
    if not S1_PATH.exists() or not S2_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixtures not present under {FIXTURES_DIR}")
    return _load_crop(80, 368, 128)


@pytest.fixture
def cloudy_region():
    # 192x192 block at row 288, col 320 — the same real region already used
    # for the despeckle/water-mask tests. Measured directly: this region has
    # a real (small) nonzero cloud fraction, so it exercises the genuine
    # disagreement path on real data, not the clean path.
    if not S1_PATH.exists() or not S2_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixtures not present under {FIXTURES_DIR}")
    return _load_crop(288, 320, 192)


def test_reconcile_real_clean_region_has_no_disagreement(clean_region):
    # Measured directly: water_fraction=0.2878, cloud_fraction=0.0,
    # confidence=1.0, optical_inconclusive=False.
    vv, s2 = clean_region
    despeckled, water, cloud_result = _run_pipeline(vv, s2)

    evidence_list = reconcile_sar_optical(despeckled, water, cloud_result)
    assert len(evidence_list) == 1
    ev = evidence_list[0]

    assert ev.payload["optical_inconclusive"] is False
    assert np.isclose(ev.payload["cloud_fraction"], 0.0)
    assert np.isclose(ev.confidence, 1.0)
    assert np.isclose(ev.payload["water_fraction"], 0.2878, atol=0.001)
    assert "no disagreement" in ev.payload["note"]


def test_reconcile_real_region_with_real_cloud_cover_is_flagged(cloudy_region):
    # This scene is NOT fully cloud-free: the same row-288/col-320 crop used
    # for the despeckle and water-mask tests has a real, nonzero cloud
    # fraction from the actual classifier output (matches the whole scene's
    # measured 1.87% overall). Measured directly here: water_fraction=0.4711,
    # cloud_fraction=0.0156, confidence=0.9844, optical_inconclusive=True.
    vv, s2 = cloudy_region
    despeckled, water, cloud_result = _run_pipeline(vv, s2)

    evidence_list = reconcile_sar_optical(despeckled, water, cloud_result)
    ev = evidence_list[0]

    assert ev.payload["optical_inconclusive"] is True
    assert np.isclose(ev.payload["cloud_fraction"], 0.0156, atol=0.001)
    assert np.isclose(ev.confidence, 0.9844, atol=0.001)
    assert np.isclose(ev.payload["water_fraction"], 0.4711, atol=0.001)
    assert "could not confirm" in ev.payload["note"]


def test_reconcile_synthetic_forced_cloud_block_flags_only_that_region(clean_region):
    """SYNTHETIC test — exercises the code path, not a real measurement.

    Takes the real, genuinely-clean SAR data from `clean_region` but replaces
    the cloud mask with a synthetic one where the top-left quarter is forced
    to "cloudy". This is constructed to test the branch logic, not observed
    from any real scene — the forced cloud fraction (0.25) and the resulting
    confidence (0.75) are exact by construction, not measurements.
    """
    vv, s2 = clean_region
    despeckled = lee_filter(vv, SarScale.DB, noise_variance=_NOISE_VARIANCE)
    water = otsu_water_mask(despeckled, SarScale.DB)

    synthetic_cloud_mask = np.zeros(vv.shape, dtype=bool)
    half = vv.shape[0] // 2
    synthetic_cloud_mask[:half, :half] = True  # force top-left quarter "cloudy"
    synthetic_probability = synthetic_cloud_mask.astype(np.float32)
    synthetic_cloud_result = CloudDetectionResult(
        probability=synthetic_probability, mask=synthetic_cloud_mask
    )

    evidence_list = reconcile_sar_optical(despeckled, water, synthetic_cloud_result)
    ev = evidence_list[0]

    assert ev.payload["optical_inconclusive"] is True
    assert np.isclose(ev.payload["cloud_fraction"], 0.25)
    assert np.isclose(ev.confidence, 0.75)
    # The SAR-derived water answer is still reported (not withheld) despite
    # the forced cloud cover.
    assert "water_mask" in ev.payload
    assert ev.payload["water_mask"].shape == water.shape


def test_reconcile_rejects_mismatched_shapes():
    despeckled = np.zeros((4, 4))
    water = np.zeros((4, 4), dtype=bool)
    mismatched_cloud_result = CloudDetectionResult(
        probability=np.zeros((5, 5), dtype=np.float32), mask=np.zeros((5, 5), dtype=bool)
    )
    with pytest.raises(ValueError):
        reconcile_sar_optical(despeckled, water, mismatched_cloud_result)
