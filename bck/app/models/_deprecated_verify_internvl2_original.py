"""AASH-001/002: verify InternVL2-2B loads and runs a forward pass in this environment.

Standalone verification script, not yet a real inference wrapper — that's later AASH work.
Run directly: `python -m app.models.verify_internvl2 [path/to/image]`.

No config type existed in app.contracts for this (checked before writing this dataclass), and
this ticket's Files field doesn't include app/contracts/**, so the config stays local here.
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass

import torch
from transformers import AutoModel, AutoTokenizer


@dataclass
class VerifyConfig:
    model_id: str = "OpenGVLab/InternVL2-2B"
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


def _cuda_mem_snapshot(label: str) -> None:
    if not torch.cuda.is_available():
        print(f"[{label}] CUDA not available — skipping VRAM snapshot")
        return
    allocated = torch.cuda.memory_allocated() / 1024**3
    reserved = torch.cuda.memory_reserved() / 1024**3
    print(f"[{label}] torch.cuda.memory_allocated = {allocated:.3f} GiB")
    print(f"[{label}] torch.cuda.memory_reserved  = {reserved:.3f} GiB")


def load_fp16(config: VerifyConfig) -> tuple[AutoModel, AutoTokenizer]:
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id, trust_remote_code=True, use_fast=False
    )
    model = (
        AutoModel.from_pretrained(
            config.model_id,
            torch_dtype=torch.float16,
            trust_remote_code=True,
        )
        .to(config.device)
        .eval()
    )
    return model, tokenizer


def load_4bit(config: VerifyConfig) -> tuple[AutoModel, AutoTokenizer]:
    from transformers import BitsAndBytesConfig

    tokenizer = AutoTokenizer.from_pretrained(
        config.model_id, trust_remote_code=True, use_fast=False
    )
    quant_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.float16)
    model = AutoModel.from_pretrained(
        config.model_id,
        quantization_config=quant_config,
        trust_remote_code=True,
    ).eval()
    return model, tokenizer


def run_caption(model: AutoModel, tokenizer: AutoTokenizer, image_path: str) -> str:
    """Real InternVL2 chat() forward pass on one real image."""
    from PIL import Image
    from torchvision.transforms import Compose, InterpolationMode, Normalize, Resize, ToTensor

    IMAGENET_MEAN = (0.485, 0.456, 0.406)
    IMAGENET_STD = (0.229, 0.224, 0.225)

    transform = Compose(
        [
            Resize((448, 448), interpolation=InterpolationMode.BICUBIC),
            ToTensor(),
            Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )
    image = Image.open(image_path).convert("RGB")
    pixel_values = transform(image).unsqueeze(0).to(torch.float16)
    if next(model.parameters()).is_cuda:
        pixel_values = pixel_values.cuda()

    generation_config = {"max_new_tokens": 64, "do_sample": False}
    question = "<image>\nDescribe this satellite image."
    return model.chat(tokenizer, pixel_values, question, generation_config)


def main() -> None:
    config = VerifyConfig()
    print(f"device = {config.device}")

    print("\n=== fp16 load ===")
    try:
        model, tokenizer = load_fp16(config)
        _cuda_mem_snapshot("after fp16 load")
    except Exception:
        print("fp16 load FAILED, full traceback:")
        traceback.print_exc()
        model = tokenizer = None

    if model is not None:
        image_path = sys.argv[1] if len(sys.argv) > 1 else None
        print("\n=== forward pass ===")
        if not image_path:
            print(
                "BLOCKED: no real image path given. Step 3 (fetching a real SEN12MS Sentinel-2 "
                "sample from mediaTUM) could not complete via wget/curl — that page is a "
                "JS-rendered SPA with no direct file link reachable without a browser. Not "
                "fabricating a placeholder image or substituting a different dataset per "
                "instructions; this step stays blocked until a real tile is provided."
            )
        else:
            try:
                caption = run_caption(model, tokenizer, image_path)
                print(f"generated caption: {caption!r}")
            except Exception:
                print("forward pass FAILED, full traceback:")
                traceback.print_exc()

    print("\n=== 4-bit bitsandbytes load ===")
    try:
        model_4bit, _ = load_4bit(config)
        _cuda_mem_snapshot("after 4-bit load")
        del model_4bit
    except Exception:
        print("4-bit load FAILED, full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
