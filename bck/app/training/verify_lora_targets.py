"""AASH-002 step 1: load InternVL3-2B and print real named modules to pick LoRA target_modules.

Standalone verification script, not the training loop. Run: `python -m app.training.verify_lora_targets`.
"""

import torch
from transformers import AutoModel

MODEL_ID = "OpenGVLab/InternVL3-2B"


def main() -> None:
    print(f"Loading {MODEL_ID}...")
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )
    print("Model OK\n")

    print("=== named modules (leaf modules only, class name shown) ===")
    seen_classes: dict[str, int] = {}
    for name, module in model.named_modules():
        children = list(module.children())
        if children:
            continue  # only leaf modules — these are the ones LoRA actually wraps
        cls = type(module).__name__
        seen_classes[cls] = seen_classes.get(cls, 0) + 1
        print(f"{name}: {cls}")

    print("\n=== leaf module class counts ===")
    for cls, count in sorted(seen_classes.items(), key=lambda kv: -kv[1]):
        print(f"{cls}: {count}")


if __name__ == "__main__":
    main()
