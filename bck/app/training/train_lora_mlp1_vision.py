"""Train the InternVL3 vision projector LoRA adapter with GSD conditioning."""

from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Literal

import torch
import torchvision.transforms as T
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

from app.training.gsd_augment import (
    DEFAULT_MAX_SIM_GSD_M,
    DEFAULT_MIN_SIM_GSD_M,
    EUROSAT_NATIVE_GSD_M,
    GSDAugmentConfig,
    MultiScaleGSDAugment,
)
from app.training.gsd_conditioning import (
    GSDConditioner,
    GSDConditioningConfig,
    attach_gsd_output_conditioning,
    condition_on,
    save_gsd_conditioner,
    validate_gsd_m,
)

MODEL_ID = "OpenGVLab/InternVL3-2B"
DATASET_ID = "Honaker/eurosat_dataset"
N_SAMPLES = 500
N_EPOCHS = 2
CHECKPOINT_EVERY = 50
IMAGE_SIZE = 448
OUTPUT_DIR = "app/training/checkpoints/yash004_mlp1_vision_lora"
LOG_PATH = "app/training/logs/mlp1_vision_loss_log.jsonl"
GSD_AUGMENT_SEED = 42
GSD_MIN_M = DEFAULT_MIN_SIM_GSD_M
GSD_MAX_M = DEFAULT_MAX_SIM_GSD_M
GSD_EMBEDDING_HIDDEN_DIM = 64
LEARNING_RATE = 1e-4

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
SplitName = Literal["train", "validation", "test"]


def build_transform(input_size: int) -> T.Compose:
    """Build the unchanged RGB resize and ImageNet normalization transform."""
    if input_size <= 0:
        raise ValueError("input_size must be positive")
    return T.Compose(
        [
            T.Lambda(lambda image: image.convert("RGB") if image.mode != "RGB" else image),
            T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def image_to_pixel_values(image: Image.Image, transform: T.Compose) -> torch.Tensor:
    """Convert one preprocessed image into InternVL's one-tile batch shape."""
    return transform(image).unsqueeze(0)


def attach_sample_gsd(sample: dict[str, Any], source_gsd_m: object) -> dict[str, Any]:
    """Attach validated physical GSD metadata at the dataset adapter boundary."""
    enriched = dict(sample)
    enriched["gsd_m"] = validate_gsd_m(source_gsd_m)
    return enriched


def preprocess_image_for_split(
    image: Image.Image,
    split: SplitName,
    transform: T.Compose,
    augmenter: MultiScaleGSDAugment | None = None,
    rng: random.Random | None = None,
) -> tuple[torch.Tensor, float | None]:
    """Apply multi-scale augmentation only for training and preserve eval preprocessing."""
    if split == "train":
        if augmenter is None or rng is None:
            raise ValueError("training preprocessing requires an augmenter and seeded RNG")
        augmented, effective_gsd_m = augmenter(image, rng)
        return image_to_pixel_values(augmented, transform), effective_gsd_m
    if split in ("validation", "test"):
        return image_to_pixel_values(image, transform), None
    raise ValueError(f"unsupported split: {split}")


def build_conditioner(model: torch.nn.Module) -> GSDConditioner:
    """Build a conditioner using the loaded model's live language hidden dimension."""
    output_dim = int(model.config.llm_config.hidden_size)
    return GSDConditioner(
        GSDConditioningConfig(
            min_gsd_m=GSD_MIN_M,
            max_gsd_m=GSD_MAX_M,
            hidden_dim=GSD_EMBEDDING_HIDDEN_DIM,
            output_dim=output_dim,
        )
    ).cuda()


def write_loss_log(log_entries: list[dict[str, Any]], path: str) -> None:
    """Write JSONL training metrics to the configured path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for entry in log_entries:
            handle.write(json.dumps(entry) + "\n")


def main() -> None:
    """Run the existing EuroSAT mlp1 LoRA training workflow with domain-gap mitigation."""
    output_path = Path(OUTPUT_DIR)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Loading tokenizer + model: {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=False)
    model = AutoModel.from_pretrained(
        MODEL_ID, trust_remote_code=True, torch_dtype=torch.float32
    ).cuda()
    model.language_model.config.use_cache = False

    model.img_context_token_id = tokenizer.convert_tokens_to_ids("<IMG_CONTEXT>")
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

    base_model = model.get_base_model()
    conditioner = build_conditioner(base_model)
    hook = attach_gsd_output_conditioning(base_model.mlp1, conditioner)
    print(f"GSD conditioner output dimension: {conditioner.config.output_dim}")

    print(f"Streaming {DATASET_ID} (real Sentinel-2 EuroSAT imagery)...")
    dataset = load_dataset(DATASET_ID, split="train", streaming=True)
    class_names = dataset.features["label"].names
    samples = list(dataset.shuffle(seed=GSD_AUGMENT_SEED, buffer_size=5000).take(N_SAMPLES))
    samples = [attach_sample_gsd(sample, EUROSAT_NATIVE_GSD_M) for sample in samples]
    seen_classes = sorted({class_names[sample["label"]] for sample in samples})
    print(f"Pulled {len(samples)} real image samples across {len(seen_classes)} classes")
    if len(seen_classes) < 2:
        raise RuntimeError(f"Shuffle did not diversify classes: {seen_classes}")

    transform = build_transform(IMAGE_SIZE)
    augmenter = MultiScaleGSDAugment(
        GSDAugmentConfig(
            source_gsd_m=EUROSAT_NATIVE_GSD_M,
            min_gsd_m=GSD_MIN_M,
            max_gsd_m=GSD_MAX_M,
            output_size=IMAGE_SIZE,
        )
    )
    rng = random.Random(GSD_AUGMENT_SEED)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad]
        + list(conditioner.parameters()),
        lr=LEARNING_RATE,
    )

    log_entries: list[dict[str, Any]] = []
    model.train()
    conditioner.train()
    total_steps = N_SAMPLES * N_EPOCHS
    step_times: list[float] = []
    global_step = 0

    for epoch in range(N_EPOCHS):
        for sample in samples:
            step_start = time.time()
            image = sample["image"]
            class_name = class_names[sample["label"]]
            pixel_values, effective_gsd_m = preprocess_image_for_split(
                image, "train", transform, augmenter, rng
            )
            pixel_values = pixel_values.to("cuda", dtype=torch.float32)
            gsd_tensor = torch.tensor([effective_gsd_m], device="cuda", dtype=torch.float32)

            question = "<image>\nWhat does this satellite image show?"
            answer = f" This satellite image shows: {class_name}."
            image_tokens = "<IMG_CONTEXT>" * num_image_token
            prompt = question.replace("<image>", f"<img>{image_tokens}</img>")
            full_text = prompt + answer
            encoded = tokenizer(full_text, return_tensors="pt", truncation=True, max_length=512).to(
                "cuda"
            )
            prompt_encoded = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
            prompt_length = prompt_encoded["input_ids"].shape[1]
            labels = encoded["input_ids"].clone()
            labels[:, :prompt_length] = -100

            optimizer.zero_grad()
            with condition_on(conditioner, gsd_tensor):
                outputs = model(
                    pixel_values=pixel_values,
                    input_ids=encoded["input_ids"],
                    attention_mask=encoded["attention_mask"],
                    image_flags=torch.ones(pixel_values.shape[0], dtype=torch.long).cuda(),
                    labels=labels,
                )
            loss = outputs.loss
            loss.backward()
            optimizer.step()

            step_time = time.time() - step_start
            step_times.append(step_time)
            log_entries.append(
                {
                    "global_step": global_step,
                    "epoch": epoch,
                    "loss": loss.item(),
                    "class": class_name,
                    "source_gsd_m": sample["gsd_m"],
                    "effective_gsd_m": round(effective_gsd_m, 4),
                    "step_seconds": round(step_time, 2),
                }
            )
            print(
                f"epoch {epoch} | step {global_step:04d}/{total_steps} | "
                f"loss {loss.item():.4f} | class={class_name} | "
                f"gsd={effective_gsd_m:.2f}m | {step_time:.2f}s"
            )

            if global_step > 0 and global_step % CHECKPOINT_EVERY == 0:
                model.save_pretrained(output_path)
                save_gsd_conditioner(conditioner, output_path)
                write_loss_log(log_entries, LOG_PATH)
            global_step += 1

    write_loss_log(log_entries, LOG_PATH)
    model.save_pretrained(output_path)
    save_gsd_conditioner(conditioner, output_path)
    hook.remove()
    print(f"Adapter and GSD conditioner checkpoint saved: {output_path}")


if __name__ == "__main__":
    main()
