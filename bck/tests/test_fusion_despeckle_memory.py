"""The masked Lee statistics compute the sum of squares without materialising every window.

The old code squared the sliding-window *view* (`windows_vals**2`), which allocates
H * W * 49 floats (~98 MiB for a 512x512 scene) and was the largest single spike of a fusion
request on the 512 MB Render instance. These tests prove the rewrite returns bit-identical
results on the real Sen1Floods11 SAR scene, and that the allocation is gone.
"""

import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import rasterio
from numpy.lib.stride_tricks import sliding_window_view

from app.tools.fusion.despeckle import _WINDOW_SIZE, _local_mean_and_variance_masked

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "Bolivia_103757_S1Hand.tif"


def _reference(array: np.ndarray, valid_mask: np.ndarray, window_size: int):
    """The previous implementation, verbatim, as the oracle."""
    effective_valid = valid_mask & np.isfinite(array)
    filled = np.where(effective_valid, array, 0.0)
    pad = window_size // 2
    padded_vals = np.pad(filled, pad, mode="reflect")
    padded_valid = np.pad(effective_valid.astype(np.float64), pad, mode="reflect")
    windows_vals = sliding_window_view(padded_vals, (window_size, window_size))
    windows_valid = sliding_window_view(padded_valid, (window_size, window_size))
    counts = windows_valid.sum(axis=(-2, -1))
    sum_vals = windows_vals.sum(axis=(-2, -1))
    sum_sq = (windows_vals**2).sum(axis=(-2, -1))
    has_support = counts > 0
    with np.errstate(invalid="ignore", divide="ignore"):
        local_mean = np.where(has_support, sum_vals / counts, 0.0)
        local_variance = np.where(has_support, sum_sq / counts - local_mean**2, 0.0)
    local_variance = np.clip(local_variance, 0.0, None)
    return local_mean, local_variance, effective_valid


@pytest.fixture
def real_linear_vv() -> tuple[np.ndarray, np.ndarray]:
    if not FIXTURE_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present at {FIXTURE_PATH}")
    with rasterio.open(FIXTURE_PATH) as dataset:
        vv_db = dataset.read(1).astype(np.float64)
    linear = np.power(10.0, vv_db / 10.0)
    return linear, np.isfinite(linear)


def test_masked_statistics_are_bit_identical_to_the_previous_implementation(real_linear_vv):
    linear, valid = real_linear_vv
    assert linear.shape == (512, 512)
    assert not valid.all(), "fixture should contain nodata, or the masked path is untested"
    new = _local_mean_and_variance_masked(linear, valid, _WINDOW_SIZE)
    old = _reference(linear, valid, _WINDOW_SIZE)
    for new_array, old_array in zip(new, old, strict=True):
        assert np.array_equal(new_array, old_array, equal_nan=True)


def test_masked_statistics_no_longer_allocate_every_window(real_linear_vv):
    linear, valid = real_linear_vv
    window_bytes = linear.size * _WINDOW_SIZE**2 * 8  # what `windows_vals**2` allocated

    tracemalloc.start()
    try:
        _local_mean_and_variance_masked(linear, valid, _WINDOW_SIZE)
        _, new_peak = tracemalloc.get_traced_memory()
        tracemalloc.reset_peak()
        _reference(linear, valid, _WINDOW_SIZE)
        _, old_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert old_peak > window_bytes  # the oracle really had the spike
    assert new_peak < window_bytes / 4
