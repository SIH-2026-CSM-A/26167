"""The composite demo pair (LEVIR-CD test split) clears the real gate with a known handoff.

Real BIT on the real fixture: if the checkpoint, the gate or the handoff geometry changes, the
demo's expected numbers change with it and this test says so.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.contracts import ImageInput, Modality
from app.pipeline.pipeline import _largest_change_component, _padded_region

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PRE = FIXTURES / "levir_cd_test_102_2_t1.jpg"
POST = FIXTURES / "levir_cd_test_102_2_t2.jpg"
CHECKPOINT = Path(__file__).resolve().parents[2] / "checkpoints" / "BIT_LEVIR" / "best_ckpt.pt"


def test_test_split_demo_pair_clears_the_gate_with_the_expected_handoff():
    for path in (PRE, POST, CHECKPOINT):
        if not path.exists():
            pytest.skip(f"required file not present at {path}")
    from app.tools.change_detection.local import detect_change

    evidence = detect_change(
        ImageInput(id="pre", modality=Modality.OPTICAL, format="JPEG", path=str(PRE)),
        ImageInput(id="post", modality=Modality.OPTICAL, format="JPEG", path=str(POST)),
        str(CHECKPOINT),
    )[0]
    assert evidence.payload["confounder_suppressed"] is False
    mask = np.asarray(evidence.payload["change_mask"], dtype=bool)
    area, bbox = _largest_change_component(mask)
    assert area == 13704
    assert area / mask.size >= 0.02
    assert bbox == (79, 0, 256, 176)
    region = _padded_region(bbox, mask_shape=mask.shape, image_size=Image.open(POST).size)
    assert region == (79, 0, 256, 176)
