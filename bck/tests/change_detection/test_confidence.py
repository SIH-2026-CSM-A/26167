import numpy as np
import pytest

from app.tools.change_detection.confidence import compute_confidence


def test_compute_confidence_mixed_predictions():
    # probability = [[0.9, 0.2], [0.6, 0.1]]
    # predicted_mask (True = predicted "changed") = [[T, F], [T, F]]
    # per-pixel confidence = P where changed, else 1-P:
    #   (0,0) changed  -> 0.9
    #   (0,1) unchanged -> 1 - 0.2 = 0.8
    #   (1,0) changed  -> 0.6
    #   (1,1) unchanged -> 1 - 0.1 = 0.9
    # mean = (0.9 + 0.8 + 0.6 + 0.9) / 4 = 3.2 / 4 = 0.8
    probability = np.array([[0.9, 0.2], [0.6, 0.1]])
    predicted_mask = np.array([[True, False], [True, False]])
    result = compute_confidence(probability, predicted_mask)
    assert np.isclose(result, 0.8)


def test_compute_confidence_all_changed_perfect_probability():
    # every pixel predicted changed with P=1.0 -> confidence = 1.0 exactly
    probability = np.ones((2, 2))
    predicted_mask = np.ones((2, 2), dtype=bool)
    result = compute_confidence(probability, predicted_mask)
    assert np.isclose(result, 1.0)


def test_compute_confidence_all_unchanged_worst_probability():
    # every pixel predicted unchanged but P=1.0 -> confidence = 1 - 1.0 = 0.0
    probability = np.ones((2, 2))
    predicted_mask = np.zeros((2, 2), dtype=bool)
    result = compute_confidence(probability, predicted_mask)
    assert np.isclose(result, 0.0)


def test_compute_confidence_rejects_shape_mismatch():
    probability = np.zeros((2, 2))
    predicted_mask = np.zeros((2, 3), dtype=bool)
    with pytest.raises(ValueError):
        compute_confidence(probability, predicted_mask)
