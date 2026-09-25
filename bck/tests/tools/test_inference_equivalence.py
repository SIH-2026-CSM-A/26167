"""Prove that sending pre-resized images to a remote model gives the model identical input.

Render resizes images before sending them to the inference Space (to_vqa_input for InternVL,
to_bit_input for BIT) and ships them as lossless PNG files. These tests compare that path with
the local path on real fixtures instead of assuming the two are equivalent.
"""

import io
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from app.contracts import ImageInput, Modality
from app.models.internvl import prepare_pixel_values
from app.tools.change_detection.bit_io import (
    decode_mask_png,
    decode_probability_png,
    encode_mask_png,
    encode_probability_png,
    to_bit_input,
)
from app.tools.change_detection.detector import build_change_evidence, detect_change
from app.tools.vqa_grounding.tool import to_vqa_input

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
LEVIR_BEFORE = REPOSITORY_ROOT / "data/demo/assets/levir_cd_train_103_9_before.png"
LEVIR_AFTER = REPOSITORY_ROOT / "data/demo/assets/levir_cd_train_103_9_after.png"
CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "checkpoints/BIT_LEVIR/best_ckpt.pt"


def _png_round_trip(image: Image.Image) -> Image.Image:
    """What the Space receives: the PNG file Render wrote, reopened."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Image.open(io.BytesIO(buffer.getvalue()))


def _non_square_fixture() -> Image.Image:
    """900x600 RGB with seeded noise over a gradient: larger than 448 and non-square, so a
    resampling or aspect difference between the two paths would show up."""
    rng = np.random.default_rng(26167)
    gradient = np.linspace(0, 255, 900, dtype=np.float32)[np.newaxis, :, np.newaxis]
    noise = rng.integers(0, 64, size=(600, 900, 3)).astype(np.float32)
    return Image.fromarray(np.clip(gradient + noise, 0, 255).astype(np.uint8), mode="RGB")


def test_vqa_render_resize_gives_internvl_identical_pixel_values():
    original = _non_square_fixture()
    local = prepare_pixel_values(original)
    remote = prepare_pixel_values(_png_round_trip(to_vqa_input(original)))
    assert local.shape == (1, 3, 448, 448)
    assert torch.equal(local, remote)


def test_bit_output_png_encoding_round_trips_within_quantization_bound():
    probability = np.random.default_rng(1).random((256, 256), dtype=np.float32)
    probability[0, :3] = [0.0, 1.0, 0.5]
    mask = probability > 0.5
    decoded = decode_probability_png(encode_probability_png(probability))
    assert np.abs(decoded - probability).max() <= 1 / 65535
    assert np.array_equal(decode_mask_png(encode_mask_png(mask)), mask)


def test_bit_remote_path_matches_local_detect_change_on_levir_fixture():
    for path in (LEVIR_BEFORE, LEVIR_AFTER, CHECKPOINT_PATH):
        if not path.exists():
            pytest.skip(f"required fixture not present at {path}")
    from app.tools.change_detection.bit_model import load_bit_model, run_bit

    image_a = ImageInput(id="pre", modality=Modality.OPTICAL, format="PNG", path=str(LEVIR_BEFORE))
    image_b = ImageInput(id="post", modality=Modality.OPTICAL, format="PNG", path=str(LEVIR_AFTER))
    net = load_bit_model(str(CHECKPOINT_PATH))

    local_probability, local_mask = run_bit(net, Image.open(LEVIR_BEFORE), Image.open(LEVIR_AFTER))

    # Remote path: Render resizes and sends PNGs; the Space runs BIT and returns PNGs.
    sent_a = _png_round_trip(to_bit_input(Image.open(LEVIR_BEFORE)))
    sent_b = _png_round_trip(to_bit_input(Image.open(LEVIR_AFTER)))
    space_probability, space_mask = run_bit(net, sent_a, sent_b)
    remote_probability = decode_probability_png(encode_probability_png(space_probability))
    remote_mask = decode_mask_png(encode_mask_png(space_mask))

    assert local_mask.any(), "fixture should contain real change, or the mask check is vacuous"
    assert np.array_equal(remote_mask, local_mask)
    assert np.abs(remote_probability - local_probability).max() <= 1 / 65535

    local_evidence = detect_change(image_a, image_b, str(CHECKPOINT_PATH))[0]
    remote_evidence = build_change_evidence(
        probability_changed=remote_probability,
        predicted_mask=remote_mask,
        image_a=image_a,
        image_b=image_b,
        started=0.0,
    )[0]
    for key in ("changed_pixel_count", "changed_percentage", "bbox", "confounder_suppressed"):
        assert remote_evidence.payload[key] == local_evidence.payload[key], key
    assert remote_evidence.confidence == pytest.approx(local_evidence.confidence, abs=1 / 65535)
