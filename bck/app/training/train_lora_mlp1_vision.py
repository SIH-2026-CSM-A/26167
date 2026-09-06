"""
YASH-004: mlp1 vision-projector LoRA training loop.
Targets InternVL3-2B's mlp1.1/mlp1.3 Linear layers (the real vision-language
projector) using REAL Sentinel-2 optical imagery (EuroSAT, Honaker/eurosat_dataset
on HF -- plain parquet, no custom loading script, verified live).

SCOPE NOTE (say this in the PR, do not bury it):
- Sentinel-1/SAR real-imagery training is NOT included in this run. BigEarthNet
  v2.0's only distribution is a 110GB monolithic archive with no partial download;
  every HF mirror checked either lacked S1 or required a deprecated loading script
  incompatible with this repo's pinned `datasets==5.0.1`. Follow-up ticket needed.
- Captions are label-derived templates ("This satellite image shows: {class}."),
  not free-text captions/QA. This is real ground truth about a real image, not
  synthetic data -- but it is a thinner training signal than a genuine caption
  would be. Say so plainly, don't oversell it.
- Does NOT touch decoder layers 26-27 (AASH-002 Path C, already done, separate file).
"""

import json
import os
import time

import torch
import torchvision.transforms as T
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

MODEL_ID = "OpenGVLab/InternVL3-2B"
DATASET_ID = "Honaker/eurosat_dataset"
N_SAMPLES = 500
N_EPOCHS = 2
CHECKPOINT_EVERY = 50
IMAGE_SIZE = 448
OUTPUT_DIR = "app/training/checkpoints/yash004_mlp1_vision_lora"
LOG_PATH = "app/training/logs/mlp1_vision_loss_log.jsonl"

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def build_transform(input_size: int) -> T.Compose:
    """Resize + normalize a real image the way InternVL's own preprocessing does."""
    return T.Compose(
        [
            T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
            T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def image_to_pixel_values(image: Image.Image, transform: T.Compose) -> torch.Tensor:
    """Single-tile preprocessing (no dynamic multi-tile splitting -- EuroSAT's
    64x64 native size doesn't need it; matches InternVL's expected (N, 3, H, W)
    input shape with N=1)."""
    return transform(image).unsqueeze(0)


print(f"Loading tokenizer + model: {MODEL_ID}")
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=False)
model = AutoModel.from_pretrained(
    MODEL_ID, trust_remote_code=True, torch_dtype=torch.float32
).cuda()
model.language_model.config.use_cache = False

img_context_token = "<IMG_CONTEXT>"
img_context_token_id = tokenizer.convert_tokens_to_ids(img_context_token)
model.img_context_token_id = img_context_token_id
num_image_token = model.num_image_token if hasattr(model, "num_image_token") else 256
print(f"num_image_token per tile (live from model): {num_image_token}")

lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["mlp1.1", "mlp1.3"],
    lora_dropout=0.05,
    bias="none",
    task_type=None,
)

print("Wrapping mlp1.1/mlp1.3 with LoRA...")
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

print(f"Streaming {DATASET_ID} (real Sentinel-2 EuroSAT imagery)...")
ds = load_dataset(DATASET_ID, split="train", streaming=True)
class_names = ds.features["label"].names
ds = ds.shuffle(seed=42, buffer_size=5000)
samples = list(ds.take(N_SAMPLES))
seen_classes = sorted({class_names[s["label"]] for s in samples})
print(
    f"Pulled {len(samples)} real image samples across {len(seen_classes)} classes: {seen_classes}"
)
if len(seen_classes) < 2:
    raise RuntimeError(
        "Shuffle did not diversify classes -- got only "
        f"{seen_classes}. Do not proceed with a single-class run."
    )

transform = build_transform(IMAGE_SIZE)

optimizer = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=1e-4)

log_entries = []
model.train()

total_steps = N_SAMPLES * N_EPOCHS
step_times = []
global_step = 0

for epoch in range(N_EPOCHS):
    for ex in samples:
        step_start = time.time()

        image = ex["image"]
        class_name = class_names[ex["label"]]

        pixel_values = image_to_pixel_values(image, transform).to("cuda", dtype=torch.float32)

        question = "<image>\nWhat does this satellite image show?"
        answer = f" This satellite image shows: {class_name}."

        image_tokens = img_context_token * num_image_token
        prompt = question.replace("<image>", f"<img>{image_tokens}</img>")
        full_text = prompt + answer

        enc = tokenizer(full_text, return_tensors="pt", truncation=True, max_length=512).to("cuda")
        prompt_enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
        prompt_len = prompt_enc["input_ids"].shape[1]

        labels = enc["input_ids"].clone()
        labels[:, :prompt_len] = -100

        optimizer.zero_grad()
        outputs = model(
            pixel_values=pixel_values,
            input_ids=enc["input_ids"],
            attention_mask=enc["attention_mask"],
            image_flags=torch.ones(pixel_values.shape[0], dtype=torch.long).cuda(),
            labels=labels,
        )
        loss = outputs.loss

        loss.backward()
        optimizer.step()

        step_time = time.time() - step_start
        step_times.append(step_time)

        entry = {
            "global_step": global_step,
            "epoch": epoch,
            "loss": loss.item(),
            "class": class_name,
            "step_seconds": round(step_time, 2),
        }
        log_entries.append(entry)
        print(
            f"epoch {epoch} | step {global_step:04d}/{total_steps} | "
            f"loss {loss.item():.4f} | class={class_name} | {step_time:.2f}s"
        )

        if global_step == 19:
            avg = sum(step_times) / len(step_times)
            projected_total_minutes = (avg * total_steps) / 60
            print(
                f"\n>>> PROJECTED TOTAL RUNTIME: {projected_total_minutes:.1f} minutes "
                f"for {total_steps} steps at {avg:.2f}s/step avg. "
                f"Abort now (interrupt kernel) if this exceeds your GPU-hour budget. <<<\n"
            )

        if global_step > 0 and global_step % CHECKPOINT_EVERY == 0:
            model.save_pretrained(OUTPUT_DIR)
            with open(LOG_PATH, "w") as f:
                for e in log_entries:
                    f.write(json.dumps(e) + "\n")
            print(f">>> Mid-run checkpoint saved at step {global_step} <<<")

        global_step += 1

with open(LOG_PATH, "w") as f:
    for entry in log_entries:
        f.write(json.dumps(entry) + "\n")
print(f"Loss log written: {LOG_PATH} ({len(log_entries)} entries)")

model.save_pretrained(OUTPUT_DIR)
print(f"Adapter checkpoint saved: {OUTPUT_DIR}")
print(f"Checkpoint dir contents: {os.listdir(OUTPUT_DIR)}")
