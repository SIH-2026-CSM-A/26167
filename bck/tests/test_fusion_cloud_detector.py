from pathlib import Path

import numpy as np
import pytest
import rasterio

from app.tools.fusion.cloud_detector import detect_clouds

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
S2CLOUDLESS_FIXTURE = FIXTURES_DIR / "s2cloudless_test_input_arrays.npz"
S2HAND_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"


def test_detect_clouds_matches_s2cloudless_reference_output():
    if not S2CLOUDLESS_FIXTURE.exists():
        pytest.skip(f"s2cloudless reference fixture not present at {S2CLOUDLESS_FIXTURE}")
    data = np.load(S2CLOUDLESS_FIXTURE)
    s2_im = data["s2_im"][0]  # drop the library's own (N, H, W, 13) batch dim
    expected_probs = data["cl_probs"][0]
    expected_mask = data["cl_mask"][0].astype(bool)

    result = detect_clouds(s2_im)

    # Tolerance matches s2cloudless's own test suite (test_cloud_detector.py):
    # assert_allclose(cloud_probs, result, rtol=1e-5) for probabilities, exact
    # equality for the binary mask. Measured max abs diff here: 2.98e-08.
    assert np.allclose(result.probability, expected_probs, rtol=1e-5)
    assert np.array_equal(result.mask, expected_mask)


def test_detect_clouds_on_real_sen1floods11_scene():
    # Real Bolivia_103757_S2Hand.tif: 13 bands, int16 (README says UInt16;
    # GDAL reports int16 here, values are all non-negative so it doesn't
    # affect correctness), TOA reflectance scaled by 10000 per the dataset's
    # own README. Measured directly: 1.87% cloud coverage (4905/262144 px).
    if not S2HAND_PATH.exists():
        pytest.skip(f"real Sen1Floods11 S2Hand fixture not present at {S2HAND_PATH}")
    with rasterio.open(S2HAND_PATH) as src:
        arr = src.read()  # (13, H, W), band order B1..B7,B8,B8A,B9,B10,B11,B12

    reflectance = np.moveaxis(arr, 0, -1).astype(np.float32) / 10000.0
    result = detect_clouds(reflectance)

    cloud_fraction = result.mask.mean()
    assert result.mask.shape == (512, 512)
    assert 0.0 <= cloud_fraction <= 1.0
    assert np.isclose(cloud_fraction, 0.0187, atol=0.001)


def test_detect_clouds_rejects_wrong_ndim():
    with pytest.raises(ValueError):
        detect_clouds(np.zeros((512, 512)))


def test_detect_clouds_rejects_wrong_band_count():
    with pytest.raises(ValueError):
        detect_clouds(np.zeros((512, 512, 7)))
