"""Global phase-correlation registration-quality gate (v1, coarse).

Method: PIL RGB load -> float32 array / 255.0 -> skimage.color.rgb2gray ->
multiply by a 2D Hann window (np.outer(np.hanning(h), np.hanning(w))) ->
skimage.registration.phase_cross_correlation(..., upsample_factor=100). The
Euclidean norm of the returned (row, col) shift is the sole gating scalar.

`error`, phase_cross_correlation's other return value, is deliberately never
used: a self-vs-self control (a real image against a byte-identical copy of
itself — zero shift, zero difference) still returned
error=0.9999999982747276 in this environment (skimage 0.26.0). The shift
computation on that same control is separately verified correct (exactly
[0, 0], norm 0.0), so `error` is not just "dominated by content dissimilarity"
here — it does not approach zero even for a literally identical pair, so it
is not a usable signal at all.

Real-pair sample (n=2 — every genuine bi-temporal _t1/_t2 pair that exists
anywhere in bck/tests/fixtures/; the directory's other fixtures are
single-timepoint SAR/optical/cloud data, not a second real timepoint of the
same modality):
  levir_test_1:       shift norm = 1.93px
  levir_train_103_9:  shift norm = 12.04px

Threshold: 40.0px, roughly 3x the maximum observed real-pair shift norm
(12.04px), rounded up. This margin is deliberately generous over a sample of
only 2 real pairs that already shows ~6x variance between them (1.93px vs
12.04px) — the point is not to falsely refuse a real, correctly co-registered
pair that happens to contain large real scene change (LEVIR-CD's
higher-shift pair is exactly that: real content change, not misregistration).
This is provisional per PRD Section 8's "TBD from real testing"; a future
ticket should widen the real-pair sample before this is treated as final.

Synthetic shift sweep (scipy.ndimage.shift, mode="reflect", levir_test_1_t1
against a shifted copy of itself) — kept for measurement-fidelity reference
only, NOT used to set the threshold above:
  1px->1.41px  2px->2.83px  4px->5.66px  8px->11.31px  16px->22.63px
  32px->45.25px

Known limitation, deliberately deferred for v1 (not built here due to time
constraints — same spirit as ARCHITECTURE.md's "Deliberately deferred"
section): this is global phase correlation over the whole frame.
Bi-temporal change-detection pairs contain large real content change by
definition, and that content change can inflate the global shift estimate
independent of true misregistration. This gate catches gross global
misalignment; it is not sensitive to subtle misregistration on a pair with
major scene change. A more robust future approach — patch-based/block-voting
phase correlation, taking a median shift across several sub-tiles to reduce
sensitivity to any one changed region — is a known, deliberately-deferred
improvement.
"""

import numpy as np
from PIL import Image
from skimage.color import rgb2gray
from skimage.registration import phase_cross_correlation

_UPSAMPLE_FACTOR = 100
_MAX_SHIFT_NORM_PX = 40.0


class RegistrationQualityError(ValueError):
    """Raised when a bi-temporal pair fails the registration-quality gate."""


def _load_gray(path: str) -> np.ndarray:
    image = Image.open(path).convert("RGB")
    array = np.asarray(image, dtype=np.float32) / 255.0
    return rgb2gray(array)


def _hann_window(shape: tuple[int, int]) -> np.ndarray:
    height, width = shape
    return np.outer(np.hanning(height), np.hanning(width))


def require_registration_quality(path_a: str, path_b: str) -> float:
    """Refuse a bi-temporal pair unless its global shift norm clears the gate.

    Returns the measured shift norm in pixels on success. Raises
    RegistrationQualityError immediately on shape mismatch (before attempting
    correlation) or when the shift norm exceeds `_MAX_SHIFT_NORM_PX`.
    """
    gray_a = _load_gray(path_a)
    gray_b = _load_gray(path_b)

    if gray_a.shape != gray_b.shape:
        raise RegistrationQualityError(
            f"image shapes differ: {gray_a.shape} vs {gray_b.shape}; "
            "cannot assess registration quality on mismatched dimensions"
        )

    window = _hann_window(gray_a.shape)
    shift, _error, _phasediff = phase_cross_correlation(
        gray_a * window, gray_b * window, upsample_factor=_UPSAMPLE_FACTOR
    )
    shift_norm_px = float(np.linalg.norm(shift))

    if shift_norm_px > _MAX_SHIFT_NORM_PX:
        raise RegistrationQualityError(
            f"global shift norm {shift_norm_px:.2f}px exceeds max "
            f"{_MAX_SHIFT_NORM_PX}px; refusing to proceed with bi-temporal "
            "change analysis"
        )
    return shift_norm_px
