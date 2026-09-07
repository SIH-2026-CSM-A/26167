from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.contracts import ImageInput, Modality
from app.tools.change_detection.change_summary import summarize_change
from app.tools.change_detection.detector import detect_change

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "checkpoints" / "BIT_LEVIR" / "best_ckpt.pt"

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


def _skip_if_missing(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            pytest.skip(f"required fixture not present at {path}")


def _detect(path_a: Path, path_b: Path):
    image_a = ImageInput(id="a", modality=Modality.OPTICAL, format="PNG", path=str(path_a))
    image_b = ImageInput(id="b", modality=Modality.OPTICAL, format="PNG", path=str(path_b))
    return detect_change(image_a, image_b, str(CHECKPOINT_PATH))[0]


def test_summarize_change_self_comparison_levir_test_1_is_unchanged():
    # Real self-comparison via detector.py's actual BIT pipeline (not a
    # synthetic mask): levir_test_1_t1 against an exact copy of itself.
    # Measured directly: 0/65536 changed pixels, 0.0000%.
    path = FIXTURES_DIR / "levir_test_1_t1.png"
    _skip_if_missing(path, CHECKPOINT_PATH)
    ev = _detect(path, path)
    assert ev.payload["status"] == "unchanged"
    assert ev.payload["changed_pixel_count"] == 0
    assert ev.payload["changed_percentage"] == 0.0


def test_summarize_change_self_comparison_levir_train_103_9_is_unchanged():
    # Real self-comparison, same method: levir_train_103_9_t1 against itself.
    # Measured directly: 0/65536 changed pixels, 0.0000%.
    path = FIXTURES_DIR / "levir_train_103_9_t1.png"
    _skip_if_missing(path, CHECKPOINT_PATH)
    ev = _detect(path, path)
    assert ev.payload["status"] == "unchanged"
    assert ev.payload["changed_pixel_count"] == 0
    assert ev.payload["changed_percentage"] == 0.0


def test_summarize_change_real_pair_levir_train_103_9_is_increased():
    # Real LEVIR-CD growth pair (the same pair ROHAN-001/ROHAN-002 verified
    # BIT against). Measured directly: status=increased, 27085/65536 changed
    # px, 41.3284%.
    path_a = FIXTURES_DIR / "levir_train_103_9_t1.png"
    path_b = FIXTURES_DIR / "levir_train_103_9_t2.png"
    _skip_if_missing(path_a, path_b, CHECKPOINT_PATH)
    ev = _detect(path_a, path_b)
    assert ev.payload["status"] == "increased"
    assert ev.payload["changed_pixel_count"] == 27085
    assert ev.payload["changed_percentage"] == pytest.approx(41.3284, abs=0.001)


def test_summarize_change_real_pair_levir_test_1_is_genuinely_unchanged():
    # levir_test_1 is NOT a growth pair in this repo's fixtures — its own
    # ground truth label is all-zero (verified in ROHAN-002). Reporting this
    # honestly rather than treating it as a second "increased" case: of the
    # two real pairs available, only levir_train_103_9 shows real detected
    # change.
    path_a = FIXTURES_DIR / "levir_test_1_t1.png"
    path_b = FIXTURES_DIR / "levir_test_1_t2.png"
    _skip_if_missing(path_a, path_b, CHECKPOINT_PATH)
    ev = _detect(path_a, path_b)
    assert ev.payload["status"] == "unchanged"


def test_summarize_change_synthetic_reversed_order_is_decreased():
    """SYNTHETIC/reversed test — exercises the direction-flip code path.

    Uses the real predicted mask from levir_train_103_9's real growth pair,
    but explicitly passes reversed_order=True to simulate a caller stating
    the image order was (t2, t1). This is a structural test of the
    direction-flip logic, NOT a validated real-world decrease observation —
    LEVIR-CD contains no real decrease pairs to test against.
    """
    path_a = FIXTURES_DIR / "levir_train_103_9_t1.png"
    path_b = FIXTURES_DIR / "levir_train_103_9_t2.png"
    _skip_if_missing(path_a, path_b, CHECKPOINT_PATH)
    ev = _detect(path_a, path_b)
    real_mask = ev.payload["change_mask"]

    reversed_result = summarize_change(real_mask, reversed_order=True)
    assert reversed_result.status == "decreased"
    # Same real pixel-level measurements as the "increased" case above —
    # only the direction label differs, per the explicit flag.
    assert reversed_result.changed_pixel_count == ev.payload["changed_pixel_count"]
    assert reversed_result.changed_percentage == pytest.approx(ev.payload["changed_percentage"])
