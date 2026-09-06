"""AASH-002 step 1: wrap InternVL3-2B with peft LoRA on mlp1.1/mlp1.3, verify it actually
loads and only those layers get trainable adapters.

Standalone verification script, not the training loop. Run:
`python -m app.training.verify_lora_wrap`.
"""

import traceback

import torch
from peft import LoraConfig, get_peft_model
from transformers import AutoModel

MODEL_ID = "OpenGVLab/InternVL3-2B"

TARGET_MODULES = ["mlp1.1", "mlp1.3"]
COMMON_KWARGS = {
    "target_modules": TARGET_MODULES,
    "r": 16,
    "lora_alpha": 32,
    "lora_dropout": 0.05,
    "bias": "none",
}


def try_wrap(model, **lora_kwargs):
    config = LoraConfig(**lora_kwargs)
    return get_peft_model(model, config)


def main() -> None:
    print(f"Loading {MODEL_ID}...")
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        trust_remote_code=True,
    )
    print("Model OK\n")

    print("=== attempt 1: task_type='FEATURE_EXTRACTION' ===")
    try:
        peft_model = try_wrap(model, task_type="FEATURE_EXTRACTION", **COMMON_KWARGS)
        print("SUCCEEDED with task_type='FEATURE_EXTRACTION'")
        peft_model.print_trainable_parameters()
        return
    except Exception:
        print("FAILED with task_type='FEATURE_EXTRACTION', full traceback:")
        traceback.print_exc()

    print("\n=== attempt 2: no task_type ===")
    try:
        peft_model = try_wrap(model, **COMMON_KWARGS)
        print("SUCCEEDED with no task_type")
        peft_model.print_trainable_parameters()
    except Exception:
        print("FAILED with no task_type, full traceback:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
