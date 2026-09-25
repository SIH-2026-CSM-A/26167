"""BIT input preparation and output encoding, shared by the local and remote paths.

Torch-free on purpose. Render resizes with to_bit_input before sending images to the
inference Space, and bit_model uses the same function locally, so both paths feed BIT
identical pixels. The Space encodes BIT's outputs as PNGs with the encoders below and
Render decodes them with the matching decoders.
"""

import io

import numpy as np
from PIL import Image

BIT_INPUT_SIZE = 256
_PROBABILITY_SCALE = 65535


def to_bit_input(image: Image.Image) -> Image.Image:
    """RGB at BIT's 256x256 input size — the resize the detector has always applied."""
    return image.convert("RGB").resize((BIT_INPUT_SIZE, BIT_INPUT_SIZE))


def encode_probability_png(probability: np.ndarray) -> bytes:
    """16-bit grayscale PNG of a [0, 1] probability map on a fixed scale (p * 65535).

    Fixed scale, never per-image min/max, so a decoded value means the same probability on
    every run. Round-off error is at most 0.5 / 65535.
    """
    quantized = np.rint(np.clip(probability, 0.0, 1.0) * _PROBABILITY_SCALE).astype(np.uint16)
    buffer = io.BytesIO()
    Image.fromarray(quantized).save(buffer, format="PNG")
    return buffer.getvalue()


def decode_probability_png(data: bytes) -> np.ndarray:
    """Inverse of encode_probability_png: float32 probabilities in [0, 1]."""
    quantized = np.asarray(Image.open(io.BytesIO(data)), dtype=np.uint16)
    return quantized.astype(np.float32) / _PROBABILITY_SCALE


def encode_mask_png(mask: np.ndarray) -> bytes:
    """8-bit PNG of a boolean mask (0 = unchanged, 1 = changed)."""
    buffer = io.BytesIO()
    Image.fromarray(mask.astype(np.uint8)).save(buffer, format="PNG")
    return buffer.getvalue()


def decode_mask_png(data: bytes) -> np.ndarray:
    """Inverse of encode_mask_png: boolean mask."""
    return np.asarray(Image.open(io.BytesIO(data))).astype(bool)
