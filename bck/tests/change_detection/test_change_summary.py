from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.tools.change_detection.change_summary import summarize_change

# Real LEVIR-CD ground-truth label used as test INPUT only — the tool never
# returns ground truth as output, it only ever describes a mask handed to it.
LABEL_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "LEVIR-CD256" / "label" / "train_103_9.png"
)


@pytest.fixture
def real_levir_mask() -> np.ndarray:
    if not LABEL_PATH.exists():
        pytest.skip(f"real LEVIR-CD sample not present at {LABEL_PATH}")
    return np.array(Image.open(LABEL_PATH))


def test_summarize_change_on_real_levir_ground_truth(real_levir_mask):
    # Verified independently against the real file (256x256, values {0, 255}):
    # changed pixels span rows 0-255 and cols 0-255, so bbox is the full frame
    # and the centroid (127.5, 127.5) falls in the middle third on both axes
    # (85.33 <= 127.5 < 170.67) -> relative_position == "centre".
    result = summarize_change(real_levir_mask)
    assert result.changed is True
    assert result.bbox == (0, 0, 255, 255)
    assert result.relative_position == "centre"
    assert "centre" in result.description
    assert "%" in result.description


def test_summarize_change_all_unchanged():
    mask = np.zeros((256, 256), dtype=np.uint8)
    result = summarize_change(mask)
    assert result.changed is False
    assert result.bbox is None
    assert result.relative_position is None
    assert result.description == "No change detected."


def test_summarize_change_rejects_non_2d_mask():
    with pytest.raises(ValueError):
        summarize_change(np.zeros((2, 3, 3)))


def test_summarize_change_relative_position_upper_left():
    mask = np.zeros((30, 30), dtype=bool)
    mask[0:3, 0:3] = True
    result = summarize_change(mask)
    assert result.bbox == (0, 0, 2, 2)
    assert result.relative_position == "upper-left"
