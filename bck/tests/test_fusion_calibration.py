import math

import numpy as np
import pytest

from app.tools.fusion.calibration import calibrate_sigma0_db


def test_calibrate_sigma0_db_normal_case():
    # DN=10, K_cal=20.0, incidence_angle_deg=30
    # dn_term  = 10*log10(10^2) = 10*log10(100) = 10*2 = 20
    # angle_term = 10*log10(sin(30 deg)) = 10*log10(0.5) = -3.0102999566398114
    # sigma0_dB = 20 - 20 + (-3.0102999566398114) = -3.0102999566398114
    expected = 10 * math.log10(10.0**2) - 20.0 + 10 * math.log10(math.sin(math.radians(30)))
    result = calibrate_sigma0_db(np.array([10.0]), k_cal=20.0, incidence_angle_deg=30.0)
    assert np.isclose(result[0], expected)
    assert np.isclose(result[0], -3.0102999566398114)


def test_calibrate_sigma0_db_dn_zero_is_nan():
    result = calibrate_sigma0_db(np.array([0.0]), k_cal=20.0, incidence_angle_deg=30.0)
    assert np.isnan(result[0])


def test_calibrate_sigma0_db_negative_dn_is_nan():
    result = calibrate_sigma0_db(np.array([-5.0]), k_cal=20.0, incidence_angle_deg=30.0)
    assert np.isnan(result[0])


@pytest.mark.parametrize("bad_angle", [0, 90, -10, 100])
def test_calibrate_sigma0_db_invalid_incidence_angle_raises(bad_angle):
    with pytest.raises(ValueError):
        calibrate_sigma0_db(np.array([10.0]), k_cal=20.0, incidence_angle_deg=bad_angle)


def test_calibrate_sigma0_db_integer_array_does_not_overflow():
    # DN=300 as int16 (300^2=90000 overflows int16's max of 32767 if squared
    # in-place); cast to float64 before squaring must avoid that entirely.
    # dn_term  = 10*log10(300^2) = 10*log10(90000) = 49.54242509439325
    # angle_term = 10*log10(sin(30 deg)) = -3.0102999566398114
    # sigma0_dB = 49.54242509439325 - 20.0 - 3.0102999566398114 = 26.532125137753438
    dn = np.array([300], dtype=np.int16)
    result = calibrate_sigma0_db(dn, k_cal=20.0, incidence_angle_deg=30.0)
    expected = 10 * math.log10(300.0**2) - 20.0 + 10 * math.log10(math.sin(math.radians(30)))
    assert np.isclose(result[0], expected)
    assert np.isclose(result[0], 26.532125137753438)


def test_calibrate_sigma0_db_rejects_array_like_k_cal():
    with pytest.raises(TypeError):
        calibrate_sigma0_db(np.array([10.0]), k_cal=[20.0], incidence_angle_deg=30.0)


def test_calibrate_sigma0_db_rejects_array_like_incidence_angle():
    with pytest.raises(TypeError):
        calibrate_sigma0_db(np.array([10.0]), k_cal=20.0, incidence_angle_deg=np.array([30.0]))
