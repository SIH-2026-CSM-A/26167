"""AASH-002 step 1: verify BigEarthNet.txt streams and inspect real annotation fields.

Standalone verification script, not the training loop. Run: `python -m app.training.verify_dataset`.
"""

from datasets import load_dataset

DATASET_ID = "BIFOLD-BigEarthNetv2-0/BigEarthNet.txt"


def main() -> None:
    print(f"Loading {DATASET_ID} with streaming=True...")
    dataset = load_dataset(DATASET_ID, split="all_data", streaming=True)
    print(f"Streaming dataset OK: {dataset}")

    for i, example in enumerate(dataset.take(5)):
        print(f"\n=== example {i} ===")
        for key, value in example.items():
            text = repr(value)
            if len(text) > 300:
                text = text[:300] + "...(truncated)"
            print(f"{key}: {text}")


if __name__ == "__main__":
    main()
