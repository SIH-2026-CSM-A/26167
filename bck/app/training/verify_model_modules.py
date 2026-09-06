"""AASH-002 step 1: full, unfiltered named_modules() dump of InternVL3-2B for real LoRA
target_modules selection.

Standalone verification script, not the training loop. Run:
`python -m app.training.verify_model_modules`.
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

    print("=== full named_modules() dump ===")
    for name, module in model.named_modules():
        print(f"{name}: {type(module).__name__}")


if __name__ == "__main__":
    main()
