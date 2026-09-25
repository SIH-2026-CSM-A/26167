"""SatQuery inference Space: InternVL3-2B (+ LoRA) VQA/grounding and BIT change detection.

Runs on CPU Basic today and on ZeroGPU after a hardware switch, with no code change:
device and dtype follow torch.cuda.is_available(), and @spaces.GPU is a no-op off ZeroGPU.
Models load once at module level. Render calls the two named endpoints with gradio_client.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from pathlib import Path

import gradio as gr
import torch
from huggingface_hub import snapshot_download
from PIL import Image

try:
    import spaces

    gpu = spaces.GPU
except ImportError:  # local runs without the spaces package

    def gpu(duration: int | None = None):
        def decorate(fn):
            return fn

        return decorate


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("satquery-inference")

WEIGHTS_REPO = os.environ.get("WEIGHTS_REPO", "ybaddam8/satquery-weights")
WEIGHTS_REVISION = os.environ.get("WEIGHTS_REVISION", "main")
EXPECTED_ADAPTER_SHA256 = "796d3c25d883d7798c3d7634f855c86f5ae2c0107922c7d5d80f216298dde405"
EXPECTED_BIT_SHA256 = "c159ba76143447f58c9f367ce8126a0014f2e4ba218cdb97cca173952c38cb3b"

# PLACEHOLDER: set from the first measured Space timings before switching to ZeroGPU.
# No-op on CPU Basic; on ZeroGPU it caps each call's GPU allocation.
VQA_GPU_DURATION_S = 120

torch.set_num_threads(os.cpu_count() or 1)

weights_dir = Path(
    snapshot_download(WEIGHTS_REPO, revision=WEIGHTS_REVISION, token=os.environ.get("HF_TOKEN"))
)
# Layout of ybaddam8/satquery-weights as uploaded.
adapter_dir = weights_dir / "lora-adapter"
bit_checkpoint = weights_dir / "bit" / "best_ckpt.pt"
os.environ["ADAPTER_PATH"] = str(adapter_dir)  # read by satquery_infer.internvl at import

from satquery_infer.bit_io import encode_mask_png, encode_probability_png  # noqa: E402
from satquery_infer.bit_model import load_bit_model, run_bit  # noqa: E402
from satquery_infer.internvl import (  # noqa: E402
    ADAPTER_NAME,
    DEFAULT_MODEL_ID,
    INTERNVL_REVISION,
    InternVLAdapter,
    InternVLModelError,
)
from satquery_infer.vqa_passes import VqaToolError, _parse_native_bbox, run_vqa_passes  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_hash(name: str, actual: str, expected: str) -> None:
    if actual == expected:
        logger.info("%s sha256 matches expected %s", name, expected)
    else:
        logger.warning("%s sha256 MISMATCH: got %s, expected %s", name, actual, expected)


adapter_sha256 = _sha256(adapter_dir / "adapter_model.safetensors")
bit_sha256 = _sha256(bit_checkpoint)
_check_hash("adapter", adapter_sha256, EXPECTED_ADAPTER_SHA256)
_check_hash("BIT checkpoint", bit_sha256, EXPECTED_BIT_SHA256)

vqa_model = InternVLAdapter()
vqa_model._ensure_loaded()
# BIT stays on CPU on every hardware: it is small, and CPU keeps its output identical to bck's
# local path (tests/tools/test_inference_equivalence.py). It never holds a ZeroGPU allocation.
bit_net = load_bit_model(str(bit_checkpoint))

MODEL_IDENTITY = {
    "base_model": DEFAULT_MODEL_ID,
    "base_revision": INTERNVL_REVISION,
    "adapter_name": ADAPTER_NAME,
    "adapter_sha256": adapter_sha256,
    "bit_sha256": bit_sha256,
    "weights_revision": WEIGHTS_REVISION,
    "device": str(vqa_model.device),
    "dtype": str(vqa_model._dtype).removeprefix("torch."),
}
logger.info("Model identity: %s", MODEL_IDENTITY)


def _open_image(path: str | None) -> Image.Image:
    if not path:
        raise gr.Error("An image file is required.")
    image = Image.open(path)
    image.load()
    return image


@gpu(duration=VQA_GPU_DURATION_S)
def vqa_ground(image_file: str, question: str) -> dict:
    """All VQA passes (answer, claim grounding, bbox for spatial questions) in one call."""
    image = _open_image(image_file)
    started = time.perf_counter()
    try:
        passes = run_vqa_passes(image=image, question=question, model=vqa_model)
    except (ValueError, VqaToolError, InternVLModelError) as error:
        raise gr.Error(str(error)) from error
    total_s = time.perf_counter() - started
    box_px = (
        _parse_native_bbox(passes.raw_bbox_output, image.size)
        if passes.raw_bbox_output is not None
        else None
    )
    return {
        "raw_answer": passes.raw_answer,
        "raw_grounding_output": passes.raw_grounding_output,
        "raw_bbox_output": passes.raw_bbox_output,
        "box_px": box_px,
        "image_size": list(image.size),
        "timings": {
            "answer_s": passes.answer_seconds,
            "grounding_s": passes.grounding_seconds,
            "bbox_s": passes.bbox_seconds,
            "total_s": total_s,
        },
        "model_identity": MODEL_IDENTITY,
    }


def change_detect(pre_file: str, post_file: str) -> dict:
    """BIT on a co-registered pair; probability as fixed-scale 16-bit PNG, mask as 8-bit PNG."""
    started = time.perf_counter()
    pre = _open_image(pre_file)
    post = _open_image(post_file)
    loaded = time.perf_counter()
    probability, mask = run_bit(bit_net, pre, post)
    inferred = time.perf_counter()
    return {
        "probability_png_b64": base64.b64encode(encode_probability_png(probability)).decode(),
        "mask_png_b64": base64.b64encode(encode_mask_png(mask)).decode(),
        "stats": {
            "changed_pixel_count": int(mask.sum()),
            "changed_fraction": float(mask.mean()),
        },
        "timings": {
            "preprocess_s": loaded - started,
            "inference_s": inferred - loaded,
            "total_s": time.perf_counter() - started,
        },
        "model_identity": MODEL_IDENTITY,
    }


with gr.Blocks(title="SatQuery inference") as demo:
    gr.Markdown(
        "SatQuery inference API. Called by the SatQuery backend; "
        "the forms below exist for manual checks."
    )
    with gr.Tab("vqa_ground"):
        vqa_image = gr.File(label="Image (PNG)", type="filepath")
        vqa_question = gr.Textbox(label="Question")
        vqa_output = gr.JSON(label="Result")
        gr.Button("Run").click(
            vqa_ground, [vqa_image, vqa_question], vqa_output, api_name="vqa_ground"
        )
    with gr.Tab("change_detect"):
        pre_image = gr.File(label="Pre image (PNG)", type="filepath")
        post_image = gr.File(label="Post image (PNG)", type="filepath")
        change_output = gr.JSON(label="Result")
        gr.Button("Run").click(
            change_detect, [pre_image, post_image], change_output, api_name="change_detect"
        )

# One request at a time: CPU Basic has 2 vCPUs and a single fp32 model instance.
demo.queue(default_concurrency_limit=1)

if __name__ == "__main__":
    demo.launch()
