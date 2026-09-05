from pathlib import Path

import numpy as np
import pytest
import rasterio

from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"
LABEL_PATH = FIXTURES_DIR / "Bolivia_103757_LabelHand.tif"

# Real region of the Bolivia_103757 chip: 192x192 block at row 288, col 320.
# Picked by scanning the chip for the largest block where both S1 bands are
# NaN-free and the LabelHand ground truth is fully labeled (no -1/no-data),
# maximizing min(water_px, nonwater_px) so the region has a genuine mix of
# both classes rather than being trivially one-sided. 661 of 36864 pixels
# have label == -1 (no-data) and are excluded from the metric; the S1 VV band
# itself has zero NaNs in this region.
_ROW0, _COL0, _SIZE = 288, 320, 192
# S1Hand is already dB-scale per the dataset's own README ("Unit: dB") —
# calibration.py is not run here, since treating already-dB values as raw DN
# would be wrong (DN<=0 handling would NaN out nearly the whole array, since
# dB backscatter is almost always negative).
_NOISE_VARIANCE = 0.005


@pytest.fixture
def real_region():
    if not S1_PATH.exists() or not LABEL_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixtures not present under {FIXTURES_DIR}")
    with rasterio.open(S1_PATH) as src:
        vv = src.read(1)[_ROW0 : _ROW0 + _SIZE, _COL0 : _COL0 + _SIZE].astype(np.float64)
    with rasterio.open(LABEL_PATH) as src:
        label = src.read(1)[_ROW0 : _ROW0 + _SIZE, _COL0 : _COL0 + _SIZE]
    assert not np.isnan(vv).any(), "region expected NaN-free VV — fixture changed?"
    return vv, label


def test_otsu_water_mask_direction_matches_known_physics(real_region):
    # Standing water reflects specularly (low backscatter); land does not.
    # Verified here against real ground truth rather than assumed.
    vv, label = real_region
    despeckled = lee_filter(vv, SarScale.DB, noise_variance=_NOISE_VARIANCE)
    valid = label != -1
    water_mean_db = despeckled[valid & (label == 1)].mean()
    nonwater_mean_db = despeckled[valid & (label == 0)].mean()
    assert water_mean_db < nonwater_mean_db


def test_otsu_water_mask_against_real_ground_truth(real_region):
    # Measured directly on this real region: IoU=0.8627, pixel accuracy=0.9319
    # (16752 ground-truth water px, 16713 predicted water px among 36203
    # validly-labeled pixels). Not an invented pass bar — the actual numbers.
    vv, label = real_region
    despeckled = lee_filter(vv, SarScale.DB, noise_variance=_NOISE_VARIANCE)
    predicted_water = otsu_water_mask(despeckled, SarScale.DB)

    valid = label != -1
    gt_water = valid & (label == 1)
    pred_water_valid = predicted_water & valid

    intersection = (gt_water & pred_water_valid).sum()
    union = (gt_water | pred_water_valid).sum()
    iou = intersection / union
    accuracy = (predicted_water[valid] == (label[valid] == 1)).mean()

    assert np.isclose(iou, 0.8627, atol=0.01)
    assert np.isclose(accuracy, 0.9319, atol=0.01)


def test_otsu_water_mask_requires_db_scale():
    from app.tools.fusion.guards import ScaleError

    array = np.array([[-10.0, -5.0], [-20.0, -1.0]])
    with pytest.raises(ScaleError):
        otsu_water_mask(array, SarScale.LINEAR)


def test_otsu_water_mask_rejects_nan():
    array = np.array([[-10.0, np.nan], [-20.0, -1.0]])
    with pytest.raises(ValueError):
        otsu_water_mask(array, SarScale.DB)
