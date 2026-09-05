"""SAR radiometric calibration: raw DN to sigma-nought dB.

Scope: valid for a single patch or scene at fixed incidence geometry only.
K_cal is a scalar by design — full-scene products with a spatially-varying
per-pixel calibration LUT are a separate future function that takes a LUT
input, not an extension of this one.
"""

import numpy as np


def _require_scalar(name: str, value: object) -> None:
    if not np.isscalar(value):
        raise TypeError(
            f"{name} must be a scalar: this function is valid only for a "
            "single patch/scene at fixed geometry, not per-pixel calibration "
            f"LUTs; got {type(value).__name__}"
        )


def calibrate_sigma0_db(dn: np.ndarray, k_cal: float, incidence_angle_deg: float) -> np.ndarray:
    """Convert raw Sentinel-1 DN to sigma-nought backscatter in dB.

    sigma0_dB = 10*log10(DN^2) - K_cal + 10*log10(sin(incidence_angle))

    DN <= 0 is physically invalid for a radar digital number and undefined
    under log10; those elements return NaN rather than emitting -inf.
    """
    _require_scalar("k_cal", k_cal)
    _require_scalar("incidence_angle_deg", incidence_angle_deg)
    if not (0 < incidence_angle_deg < 90):
        raise ValueError(
            f"incidence_angle_deg must be in the open interval (0, 90); got {incidence_angle_deg}"
        )

    dn = np.asarray(dn, dtype=np.float64)
    valid = dn > 0
    dn_term_db = np.full(dn.shape, np.nan, dtype=np.float64)
    dn_term_db[valid] = 10.0 * np.log10(np.square(dn[valid]))

    angle_term_db = 10.0 * np.log10(np.sin(np.deg2rad(incidence_angle_deg)))

    return dn_term_db - k_cal + angle_term_db
