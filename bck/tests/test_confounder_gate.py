from pathlib import Path

import numpy as np
import pytest
import rasterio
from PIL import Image

from app.tools.change_detection.confounder_gate import (
    _FALSE_CHANGE_AREA_THRESHOLD,
    evaluate_confounder_gate,
    filter_confounder_mask,
    normalize_radiometry,
)
from app.tools.change_detection.registration_quality import RegistrationQualityError
from app.tools.fusion.cloud_detector import detect_clouds

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
S2_BOLIVIA_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"
SEN12MS_CR_PATH = FIXTURES_DIR / "sen12ms_cr_sample.npz"
LEVIR_T1_PATH = FIXTURES_DIR / "levir_test_1_t1.png"
LEVIR_T2_PATH = FIXTURES_DIR / "levir_test_1_t2.png"
LEVIR_GROWTH_T1 = FIXTURES_DIR / "levir_train_103_9_t1.png"
LEVIR_GROWTH_T2 = FIXTURES_DIR / "levir_train_103_9_t2.png"
LEVIR_SHIFTED = FIXTURES_DIR / "levir_test_1_t1_SYNTHETIC_shifted_32px.png"
LEVIR_RESIZED = FIXTURES_DIR / "levir_test_1_t1_SYNTHETIC_resized_200.png"


def _skip_if_missing(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            pytest.skip(f"required fixture not present at {path}")


def test_real_sen1floods11_cloud_confounder_suppresses_false_change():
    """Real Sen1Floods11 satellite scene: cloud confounder is NOT reported as change."""
    _skip_if_missing(S2_BOLIVIA_PATH)
    with rasterio.open(S2_BOLIVIA_PATH) as src:
        arr = src.read()

    reflectance = np.moveaxis(arr, 0, -1).astype(np.float32) / 10000.0
    cloud_result = detect_clouds(reflectance)
    assert cloud_result.mask.sum() == 4905  # Measured 1.87% real cloud cover

    # Cloud pixels create false change if unmasked; with gate, cloud pixels are excluded
    raw_cloud_change = cloud_result.mask.copy()
    gate_result = evaluate_confounder_gate(
        raw_mask=raw_cloud_change,
        cloud_mask=cloud_result.mask,
    )
    assert gate_result.suppressed is True
    assert gate_result.passed is False
    assert gate_result.changed_pixel_count == 0
    assert gate_result.changed_percentage == 0.0
    assert "suppressed as false change" in gate_result.reason


def test_real_sen1floods11_seasonal_illumination_suppressed_by_radiometric_norm():
    """Real Sen1Floods11 scene: seasonal illumination variance eliminated via RRN."""
    _skip_if_missing(S2_BOLIVIA_PATH)
    with rasterio.open(S2_BOLIVIA_PATH) as src:
        arr = src.read().astype(np.float32)

    # Physical winter vs summer solar zenith angle factor: cos(55 deg) / cos(25 deg)
    winter_attenuation = 0.6328
    winter_scene = arr * winter_attenuation

    # Without normalization, illumination drop triggers large false change
    raw_delta = np.abs(arr[0] - winter_scene[0]) > 50.0
    unnormalized_change_frac = raw_delta.mean()
    assert unnormalized_change_frac > 0.20  # >20% spurious change from illumination alone

    # With Relative Radiometric Normalization, seasonal variance is eliminated
    _, norm_winter = normalize_radiometry(arr, winter_scene)
    norm_delta = np.abs(arr - norm_winter)
    assert norm_delta.max() < 1e-2

    normalized_mask = norm_delta[0] > 1.0  # Zero pixels exceed threshold
    gate_result = evaluate_confounder_gate(raw_mask=normalized_mask)
    assert gate_result.suppressed is True
    assert gate_result.changed_pixel_count == 0
    assert gate_result.changed_percentage == 0.0


def test_real_sen12ms_cr_complete_cloud_obstruction_suppresses_detection():
    """Real SEN12MS-CR 100% cloud-covered scene correctly suppresses change detection."""
    _skip_if_missing(SEN12MS_CR_PATH)
    data = np.load(SEN12MS_CR_PATH)
    s2_cloudy = data["s2_cloudy"]
    cloud_result = detect_clouds(s2_cloudy)
    assert cloud_result.mask.mean() == 1.0  # 100% cloud obstruction

    raw_mask = np.ones((256, 256), dtype=bool)
    gate_result = evaluate_confounder_gate(raw_mask=raw_mask, cloud_mask=cloud_result.mask)
    assert gate_result.suppressed is True
    assert gate_result.valid_pixel_fraction == 0.0
    assert "Complete scene obstruction" in gate_result.reason


def test_real_levir_growth_pair_clears_confounder_gate():
    """Real LEVIR-CD growth pair (41.33% change) passes confounder precision gate."""
    _skip_if_missing(LEVIR_GROWTH_T1, LEVIR_GROWTH_T2)
    # Measured directly: train_103_9 has 27085 / 65536 = 41.328% changed pixels
    label_path = FIXTURES_DIR / "levir_train_103_9_label.png"
    _skip_if_missing(label_path)
    real_growth_mask = np.array(Image.open(label_path)) > 0

    gate_result = evaluate_confounder_gate(
        raw_mask=real_growth_mask,
        path_a=str(LEVIR_GROWTH_T1),
        path_b=str(LEVIR_GROWTH_T2),
    )
    assert gate_result.passed is True
    assert gate_result.suppressed is False
    assert gate_result.changed_percentage == pytest.approx(39.95, abs=0.5)
    assert gate_result.registration_shift_px == pytest.approx(12.04, abs=0.05)
    assert "exceeds confounder precision threshold" in gate_result.reason


def test_real_levir_test_1_no_change_is_suppressed():
    """Real LEVIR-CD no-change pair is correctly suppressed as unchanged."""
    _skip_if_missing(LEVIR_T1_PATH, LEVIR_T2_PATH)
    zero_mask = np.zeros((256, 256), dtype=bool)
    gate_result = evaluate_confounder_gate(
        raw_mask=zero_mask,
        path_a=str(LEVIR_T1_PATH),
        path_b=str(LEVIR_T2_PATH),
    )
    assert gate_result.suppressed is True
    assert gate_result.changed_pixel_count == 0
    assert gate_result.registration_shift_px == pytest.approx(1.93, abs=0.05)


def test_confounder_gate_rejection_on_registration_failure():
    """Reuses ROHAN-004 registration quality gate: aborts when shift exceeds 40px."""
    _skip_if_missing(LEVIR_T1_PATH, LEVIR_SHIFTED)
    raw_mask = np.zeros((256, 256), dtype=bool)
    with pytest.raises(RegistrationQualityError, match="exceeds max 40.0px"):
        evaluate_confounder_gate(
            raw_mask=raw_mask,
            path_a=str(LEVIR_T1_PATH),
            path_b=str(LEVIR_SHIFTED),
        )


def test_confounder_gate_rejection_on_shape_mismatch():
    """Reuses ROHAN-004 registration quality gate: rejects mismatched dimensions."""
    _skip_if_missing(LEVIR_T1_PATH, LEVIR_RESIZED)
    raw_mask = np.zeros((256, 256), dtype=bool)
    with pytest.raises(RegistrationQualityError, match="shapes differ"):
        evaluate_confounder_gate(
            raw_mask=raw_mask,
            path_a=str(LEVIR_T1_PATH),
            path_b=str(LEVIR_RESIZED),
        )


def test_precision_decision_threshold_boundary():
    """Precision over recall: change below 2.0% is suppressed, above 2.0% is accepted."""
    mask_size = 10000
    sub_threshold_count = int(mask_size * (_FALSE_CHANGE_AREA_THRESHOLD - 0.005))
    above_threshold_count = int(mask_size * (_FALSE_CHANGE_AREA_THRESHOLD + 0.005))

    sub_mask = np.zeros((100, 100), dtype=bool)
    sub_mask.flat[:sub_threshold_count] = True
    result_sub = evaluate_confounder_gate(raw_mask=sub_mask)
    assert result_sub.suppressed is True
    assert result_sub.passed is False

    above_mask = np.zeros((100, 100), dtype=bool)
    above_mask.flat[:above_threshold_count] = True
    result_above = evaluate_confounder_gate(raw_mask=above_mask)
    assert result_above.suppressed is False
    assert result_above.passed is True


def test_filter_confounder_mask_rejects_non_2d():
    with pytest.raises(ValueError, match="raw_mask must be 2D"):
        filter_confounder_mask(np.zeros((2, 3, 3)))
