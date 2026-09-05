"""SAR speckle suppression: standard Lee filter.

Source: Lee, J.S. (1980), "Digital image enhancement and noise filtering by
use of local statistics," IEEE Transactions on Pattern Analysis and Machine
Intelligence, PAMI-2(2).

Pipeline order is calibrate-to-dB (calibration.py) then despeckle: this
function requires its input already declared as dB scale and refuses
otherwise, via `require_db_scale`. Window size (7x7) is a fixed, authorised
decision, not a caller parameter.
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from app.tools.fusion.guards import require_db_scale
from app.tools.fusion.sar_scale import SarScale

_WINDOW_SIZE = 7


def _local_mean_and_variance(array: np.ndarray, window_size: int) -> tuple[np.ndarray, np.ndarray]:
    pad = window_size // 2
    padded = np.pad(array, pad, mode="reflect")
    windows = sliding_window_view(padded, (window_size, window_size))
    local_mean = windows.mean(axis=(-2, -1))
    local_variance = windows.var(axis=(-2, -1))
    return local_mean, local_variance


def lee_filter(
    sigma0_db: np.ndarray, declared_scale: SarScale, noise_variance: float
) -> np.ndarray:
    """Apply a 7x7 Lee filter to a dB-scale SAR array: dB -> linear -> Lee -> dB.

    output = local_mean + k * (pixel - local_mean)
    k = local_variance / (local_variance + noise_variance)

    `noise_variance` is a required scalar with no invented default. NaNs in
    `sigma0_db` (e.g. from calibration.py's DN<=0 handling) propagate to every
    pixel whose 7x7 window includes them — this filter does not mask NaNs.
    """
    require_db_scale(sigma0_db, declared_scale)
    if not np.isscalar(noise_variance):
        raise TypeError(f"noise_variance must be a scalar; got {type(noise_variance).__name__}")
    if noise_variance <= 0:
        raise ValueError(f"noise_variance must be positive; got {noise_variance}")

    sigma0_db = np.asarray(sigma0_db, dtype=np.float64)
    linear = np.power(10.0, sigma0_db / 10.0)

    local_mean, local_variance = _local_mean_and_variance(linear, _WINDOW_SIZE)
    k = local_variance / (local_variance + noise_variance)
    filtered_linear = local_mean + k * (linear - local_mean)

    return 10.0 * np.log10(filtered_linear)
