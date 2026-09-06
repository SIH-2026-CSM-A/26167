from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.contracts import EvidenceType, ImageInput, Modality
from app.tools.change_detection.detector import detect_change

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
CHECKPOINT_PATH = Path(__file__).resolve().parents[1] / "checkpoints" / "BIT_LEVIR" / "best_ckpt.pt"


def _image_input(image_id: str, filename: str) -> ImageInput:
    return ImageInput(
        id=image_id, modality=Modality.OPTICAL, format="PNG", path=str(FIXTURES_DIR / filename)
    )


def _skip_if_fixtures_missing(*paths: Path) -> None:
    for path in paths:
        if not path.exists():
            pytest.skip(f"required fixture not present at {path}")


def test_detect_change_real_pair_with_no_change_matches_ground_truth():
    # Real LEVIR-CD pair already committed for the frontend (fnt/test-fixtures/
    # levir_test_1_*), copied here for a self-contained backend test. Its
    # ground truth label is genuinely all-zero (verified: np.unique == [0]) —
    # this is a real no-change pair, not a degenerate/broken result.
    image_a = _image_input("t1", "levir_test_1_t1.png")
    image_b = _image_input("t2", "levir_test_1_t2.png")
    _skip_if_fixtures_missing(
        FIXTURES_DIR / "levir_test_1_t1.png", FIXTURES_DIR / "levir_test_1_t2.png", CHECKPOINT_PATH
    )

    evidence_list = detect_change(image_a, image_b, str(CHECKPOINT_PATH))
    assert len(evidence_list) == 1
    ev = evidence_list[0]

    assert ev.tool == "change_detection.bit"
    assert ev.type is EvidenceType.MASK
    mask = ev.payload["change_mask"]
    assert mask.mean() == 0.0
    assert ev.payload["description"] == "No change detected."


def test_detect_change_real_pair_with_change_matches_ground_truth_closely():
    # Real LEVIR-CD sample (train_103_9), the same pair ROHAN-001 verified BIT
    # against directly via its CLI demo (41.3% predicted change there).
    # Measured directly here via detector.py: predicted=41.33% changed,
    # ground truth=39.95% changed, IoU=0.8945, pixel accuracy=0.9548,
    # confidence=0.9523.
    image_a = _image_input("t1", "levir_train_103_9_t1.png")
    image_b = _image_input("t2", "levir_train_103_9_t2.png")
    label_path = FIXTURES_DIR / "levir_train_103_9_label.png"
    _skip_if_fixtures_missing(
        FIXTURES_DIR / "levir_train_103_9_t1.png",
        FIXTURES_DIR / "levir_train_103_9_t2.png",
        label_path,
        CHECKPOINT_PATH,
    )

    evidence_list = detect_change(image_a, image_b, str(CHECKPOINT_PATH))
    ev = evidence_list[0]
    mask = ev.payload["change_mask"]
    ground_truth = np.array(Image.open(label_path)) > 0

    intersection = (mask & ground_truth).sum()
    union = (mask | ground_truth).sum()
    iou = intersection / union
    accuracy = (mask == ground_truth).mean()

    assert np.isclose(mask.mean(), 0.4133, atol=0.001)
    assert np.isclose(iou, 0.8945, atol=0.001)
    assert np.isclose(accuracy, 0.9548, atol=0.001)
    assert np.isclose(ev.confidence, 0.9523, atol=0.001)
    assert "41.3%" in ev.payload["description"]
