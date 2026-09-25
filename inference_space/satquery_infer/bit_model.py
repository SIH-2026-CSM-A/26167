"""BIT forward pass: the only torch-dependent part of change detection.

Takes two images, returns the per-pixel change probability and BIT's predicted mask.
Everything after that (confounder gate, confidence, summary, Evidence) lives in the
torch-free detector.build_change_evidence so it can run where torch is not installed.
"""

from types import SimpleNamespace

import numpy as np
import torch
from PIL import Image

from satquery_infer.bit_io import to_bit_input
from bit_vendor.networks import define_G

_NET_G = "base_transformer_pos_s4_dd8_dedim8"
_NORMALIZE_MEAN = 0.5
_NORMALIZE_STD = 0.5


def image_to_tensor(image: Image.Image) -> torch.Tensor:
    """Prepare an image as BIT expects: 256x256 RGB scaled to [-1, 1], NCHW."""
    array = np.asarray(to_bit_input(image), dtype=np.float32) / 255.0
    normalized = (array - _NORMALIZE_MEAN) / _NORMALIZE_STD
    return torch.from_numpy(normalized).permute(2, 0, 1).unsqueeze(0).float()


def load_bit_model(checkpoint_path: str) -> torch.nn.Module:
    """Build BIT's network and load its pretrained LEVIR-CD weights."""
    net = define_G(SimpleNamespace(net_G=_NET_G))
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    net.load_state_dict(checkpoint["model_G_state_dict"])
    net.eval()
    return net


def run_bit(
    net: torch.nn.Module, image_a: Image.Image, image_b: Image.Image
) -> tuple[np.ndarray, np.ndarray]:
    """Return (probability of change as float32 HxW, predicted boolean mask HxW)."""
    tensor_a = image_to_tensor(image_a)
    tensor_b = image_to_tensor(image_b)
    with torch.no_grad():
        logits = net(tensor_a, tensor_b)
        probability_changed = torch.softmax(logits, dim=1)[0, 1].numpy()
        predicted_mask = torch.argmax(logits, dim=1)[0].numpy().astype(bool)
    return probability_changed, predicted_mask
