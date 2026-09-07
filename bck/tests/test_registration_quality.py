from pathlib import Path

import pytest

from app.tools.change_detection.registration_quality import (
    RegistrationQualityError,
    require_registration_quality,
)

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _skip_if_missing(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            pytest.skip(f"required fixture not present at {path}")


def test_require_registration_quality_real_levir_test_1_passes():
    # Measured directly: shift_norm_px = 1.9304 (well under the 40.0px gate).
    path_a = FIXTURES_DIR / "levir_test_1_t1.png"
    path_b = FIXTURES_DIR / "levir_test_1_t2.png"
    _skip_if_missing(path_a, path_b)
    result = require_registration_quality(str(path_a), str(path_b))
    assert result == pytest.approx(1.9304, abs=0.001)


def test_require_registration_quality_real_levir_train_103_9_passes():
    # Measured directly: shift_norm_px = 12.0354 (under the 40.0px gate,
    # despite this being LEVIR-CD's higher-shift real pair with real scene
    # change — exactly the case the threshold's margin exists to not refuse).
    path_a = FIXTURES_DIR / "levir_train_103_9_t1.png"
    path_b = FIXTURES_DIR / "levir_train_103_9_t2.png"
    _skip_if_missing(path_a, path_b)
    result = require_registration_quality(str(path_a), str(path_b))
    assert result == pytest.approx(12.0354, abs=0.001)


def test_require_registration_quality_rejects_shape_mismatch():
    # SYNTHETIC fixture: levir_test_1_t1 resized to 200x200 (deliberately
    # constructed to exercise the shape-mismatch refusal path; not a real
    # measurement).
    path_a = FIXTURES_DIR / "levir_test_1_t1.png"
    path_b = FIXTURES_DIR / "levir_test_1_t1_SYNTHETIC_resized_200.png"
    _skip_if_missing(path_a, path_b)
    with pytest.raises(RegistrationQualityError, match="shapes differ"):
        require_registration_quality(str(path_a), str(path_b))


def test_require_registration_quality_refuses_gross_synthetic_shift():
    # SYNTHETIC fixture: levir_test_1_t1 shifted 32px via scipy.ndimage.shift
    # (mode="reflect") against itself — deliberately constructed gross
    # misregistration, not a real measurement. Measured directly here:
    # shift_norm_px = 45.25, exceeding the 40.0px gate (matches the module
    # docstring's reference synthetic sweep exactly).
    path_a = FIXTURES_DIR / "levir_test_1_t1.png"
    path_b = FIXTURES_DIR / "levir_test_1_t1_SYNTHETIC_shifted_32px.png"
    _skip_if_missing(path_a, path_b)
    with pytest.raises(RegistrationQualityError, match="exceeds max"):
        require_registration_quality(str(path_a), str(path_b))
