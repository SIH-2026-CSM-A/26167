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


def _local_mean_and_variance_masked(
    array: np.ndarray, valid_mask: np.ndarray, window_size: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Same statistics as `_local_mean_and_variance`, but each window average only
    over its own valid, finite members instead of all `window_size**2` cells.

    Returns `(local_mean, local_variance, effective_valid)`, where
    `effective_valid` is `valid_mask` narrowed to pixels that are also finite —
    a pixel `valid_mask` claims is valid but that is NaN/inf is still invalid.
    """
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
    # Float roundoff on a near-zero true variance can go slightly negative.
    local_variance = np.clip(local_variance, 0.0, None)
    return local_mean, local_variance, effective_valid


def lee_filter(
    sigma0_db: np.ndarray,
    declared_scale: SarScale,
    noise_variance: float,
    valid_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Apply a 7x7 Lee filter to a dB-scale SAR array: dB -> linear -> Lee -> dB.

    output = local_mean + k * (pixel - local_mean)
    k = local_variance / (local_variance + noise_variance)

    `noise_variance` is a required scalar with no invented default. Without
    `valid_mask`, NaNs in `sigma0_db` (e.g. from calibration.py's DN<=0
    handling) propagate to every pixel whose 7x7 window includes them — this
    is the legacy behavior, preserved when no mask is given.

    With `valid_mask` (a co-registered boolean array, True = valid data), each
    window statistic is computed only from that window's valid, finite
    members, so a NaN/nodata pixel never leaks into a neighbouring valid
    pixel's filtered value. Pixels outside `valid_mask` are never estimated
    from neighbours and always come back NaN in the output — never
    zero-filled — since there is nothing there to filter.
    """
    require_db_scale(sigma0_db, declared_scale)
    if not np.isscalar(noise_variance):
        raise TypeError(f"noise_variance must be a scalar; got {type(noise_variance).__name__}")
    if noise_variance <= 0:
        raise ValueError(f"noise_variance must be positive; got {noise_variance}")

    sigma0_db = np.asarray(sigma0_db, dtype=np.float64)
    linear = np.power(10.0, sigma0_db / 10.0)

    if valid_mask is None:
        local_mean, local_variance = _local_mean_and_variance(linear, _WINDOW_SIZE)
        k = local_variance / (local_variance + noise_variance)
        filtered_linear = local_mean + k * (linear - local_mean)
        return 10.0 * np.log10(filtered_linear)

    valid_mask = np.asarray(valid_mask, dtype=bool)
    if valid_mask.shape != sigma0_db.shape:
        raise ValueError(
            f"valid_mask must share sigma0_db's shape {sigma0_db.shape}; got {valid_mask.shape}"
        )
    local_mean, local_variance, effective_valid = _local_mean_and_variance_masked(
        linear, valid_mask, _WINDOW_SIZE
    )
    k = local_variance / (local_variance + noise_variance)
    filtered_linear = local_mean + k * (linear - local_mean)
    with np.errstate(invalid="ignore", divide="ignore"):
        filtered_db = 10.0 * np.log10(filtered_linear)
    return np.where(effective_valid, filtered_db, np.nan)
