from pathlib import Path

import numpy as np
import pytest
import rasterio

from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.guards import ScaleError
from app.tools.fusion.sar_scale import SarScale

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "Bolivia_103757_S1Hand.tif"

# Fixed clean sub-window of the real Sen1Floods11 Bolivia_103757 chip, verified
# NaN-free in both bands. The chip's no-data region (nodata=NaN) covers ~61%
# of the full 512x512 extent; this 64x64 block at row 0, col 384 falls
# entirely within the valid footprint.
_ROW0, _COL0, _SIZE = 0, 384, 64


@pytest.fixture
def real_vv_block() -> np.ndarray:
    if not FIXTURE_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present at {FIXTURE_PATH}")
    with rasterio.open(FIXTURE_PATH) as src:
        arr = src.read(1)  # band 1 (rasterio 1-indexed) = VV, per the dataset README
    block = arr[_ROW0 : _ROW0 + _SIZE, _COL0 : _COL0 + _SIZE].astype(np.float64)
    assert not np.isnan(block).any(), "fixture's known-clean block contains NaN — fixture changed?"
    return block


def test_lee_filter_reduces_variance_on_real_sar_data(real_vv_block):
    # Real Sen1Floods11 Bolivia_103757_S1Hand.tif, VV band, dB scale per the
    # dataset's own README ("Unit: dB"). noise_variance=0.005 is a fixed test
    # constant, same order of magnitude as this block's linear-domain variance
    # (~0.00626) — chosen to produce a real, non-trivial reduction.
    # Measured directly: before mean=-8.980 var=6.975, after mean=-8.599 var=2.904.
    before_var = real_vv_block.var()
    before_mean = real_vv_block.mean()

    filtered = lee_filter(real_vv_block, SarScale.DB, noise_variance=0.005)

    after_var = filtered.var()
    after_mean = filtered.mean()

    assert after_var < before_var
    assert abs(after_mean - before_mean) < 1.0


def test_lee_filter_requires_db_scale(real_vv_block):
    with pytest.raises(ScaleError):
        lee_filter(real_vv_block, SarScale.LINEAR, noise_variance=0.005)


def test_lee_filter_rejects_non_scalar_noise_variance(real_vv_block):
    with pytest.raises(TypeError):
        lee_filter(real_vv_block, SarScale.DB, noise_variance=np.array([0.005]))


def test_lee_filter_rejects_non_positive_noise_variance(real_vv_block):
    with pytest.raises(ValueError):
        lee_filter(real_vv_block, SarScale.DB, noise_variance=0.0)
