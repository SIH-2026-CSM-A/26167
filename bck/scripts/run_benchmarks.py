"""
YASH-007 (F25): RSVQA-LR benchmark evaluation for the YASH-004 mlp1 vision-projector
LoRA adapter.

SCOPE: this covers AC2 (RSVQA-LR) only. AC1 (BigEarthNet.txt manually-verified
benchmark split) is out of scope for this ticket and owned by ROHAN-008 -- do not
extend this script to BigEarthNet.txt.

Standalone script, same pattern as app/training/train_lora_mlp1_vision.py: not
imported by the running application, meant to be run manually on a GPU-backed
Colab/Kaggle session (WSL2 on this dev machine OOMs loading InternVL3-2B,
confirmed separately -- this script is not runnable in that environment).

Downloads the official RSVQA-LR files directly from Zenodo record 6344334
(https://zenodo.org/records/6344334), loads the base model + the YASH-004 LoRA
adapter (merged to main via PR #48, commit b60d9ae -- r=16/alpha=32 on
mlp1.1/mlp1.3), runs greedy (do_sample=False) generation over the *active*
test-split examples (see app/evaluation/rsvqa_lr.py's docstring for why "active"
matters -- the raw file lists 33,212 test-split question rows but only 10,004 are
real), scores them (count-type answers scored by the RSVQA paper's bucketed-range
convention, not raw exact match), and writes
app/evaluation/results/rsvqa_lr.json.

Before scoring, the loaded active-record counts are checked against the verified
expectation (100 images / 10,004 questions) and the run aborts loudly if they don't
match -- never silently reporting a score against an unverified slice.

Run from bck/, for the real AC2 score (full active slice, no --slice-size):
    uv run python scripts/run_benchmarks.py

For a quick diagnostic run against a smaller fixed-seed subset (NOT the AC2 score --
the output JSON's `is_full_active_slice` will be false):
    uv run python scripts/run_benchmarks.py --slice-size 200
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import torch
import torchvision.transforms as T
from peft import PeftModel
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

# Allow `import app.evaluation` when this script is run directly (its own directory,
# not bck/, is what Python puts on sys.path by default).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.evaluation import (  # noqa: E402
    Prediction,
    build_prompt,
    load_active_test_examples,
    score_predictions,
    select_subset,
    validate_active_counts,
    write_results,
)

MODEL_ID = "OpenGVLab/InternVL3-2B"
ADAPTER_PATH = "app/training/checkpoints/yash004_mlp1_vision_lora"
DATA_DIR = Path("data/rsvqa_lr")
IMAGES_ZIP_URL = "https://zenodo.org/api/records/6344334/files/Images_LR.zip/content"
SPLIT_FILE_URLS = {
    "LR_split_test_images.json": (
        "https://zenodo.org/api/records/6344334/files/LR_split_test_images.json/content"
    ),
    "LR_split_test_questions.json": (
        "https://zenodo.org/api/records/6344334/files/LR_split_test_questions.json/content"
    ),
    "LR_split_test_answers.json": (
        "https://zenodo.org/api/records/6344334/files/LR_split_test_answers.json/content"
    ),
}
RESULTS_PATH = Path("app/evaluation/results/rsvqa_lr.json")

IMAGE_SIZE = 448
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
MAX_NEW_TOKENS = 16  # RSVQA-LR answers are one or two words / a single number
DEFAULT_SEED = 42


def download_rsvqa_lr(data_dir: Path) -> None:
    """Fetch the official RSVQA-LR split files and images archive, skipping what exists."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename, url in SPLIT_FILE_URLS.items():
        dest = data_dir / filename
        if dest.exists():
            continue
        print(f"Downloading {filename} from {url} ...")
        urllib.request.urlretrieve(url, dest)

    images_dir = data_dir / "Images_LR"
    if not images_dir.exists():
        zip_path = data_dir / "Images_LR.zip"
        if not zip_path.exists():
            print(f"Downloading Images_LR.zip from {IMAGES_ZIP_URL} ...")
            urllib.request.urlretrieve(IMAGES_ZIP_URL, zip_path)
        print("Extracting Images_LR.zip ...")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(data_dir)


def get_git_commit_hash() -> str | None:
    """Real current HEAD hash for the results JSON's audit trail, or None if unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).resolve().parent,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def build_transform(input_size: int) -> T.Compose:
    """Same preprocessing as app/training/train_lora_mlp1_vision.py's build_transform."""
    return T.Compose(
        [
            T.Lambda(lambda img: img.convert("RGB") if img.mode != "RGB" else img),
            T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
            T.ToTensor(),
            T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def load_model_and_tokenizer(adapter_path: str) -> tuple[object, object]:
    """Load the InternVL3-2B base model, apply the YASH-004 LoRA adapter, and eval() it."""
    print(f"Loading tokenizer + base model: {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=False)
    model = AutoModel.from_pretrained(
        MODEL_ID, trust_remote_code=True, torch_dtype=torch.float32
    ).cuda()

    img_context_token_id = tokenizer.convert_tokens_to_ids("<IMG_CONTEXT>")
    model.img_context_token_id = img_context_token_id

    print(f"Loading LoRA adapter: {adapter_path}")
    model = PeftModel.from_pretrained(model, adapter_path)
    model.eval()
    return model, tokenizer


def generate_answer(
    *,
    model: object,
    tokenizer: object,
    image: Image.Image,
    prompt: str,
    transform: T.Compose,
) -> str:
    """Run one greedy-decoded generation pass (do_sample=False -- deterministic, no
    sampling, matching AC2's reproducibility requirement: rerunning against the same
    slice must reproduce the same score)."""
    pixel_values = transform(image).unsqueeze(0).to("cuda", dtype=torch.float32)
    generation_config = {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False}
    with torch.inference_mode():
        response = model.chat(tokenizer, pixel_values, prompt, generation_config)
    text = response[0] if isinstance(response, tuple) else response
    return str(text).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--slice-size",
        type=int,
        default=None,
        help=(
            "Number of active test examples to evaluate. Omit for the real AC2 run "
            "(full 10,004-question active slice). Passing a smaller number produces "
            "a diagnostic-only score, clearly marked as such in the output JSON."
        ),
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Subset selection seed.")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--adapter-path", type=str, default=ADAPTER_PATH)
    parser.add_argument("--results-path", type=Path, default=RESULTS_PATH)
    args = parser.parse_args()

    if not Path(args.adapter_path).exists():
        raise SystemExit(
            f"LoRA adapter not found at {args.adapter_path!r}. Run "
            "app/training/train_lora_mlp1_vision.py first, or pass --adapter-path."
        )

    download_rsvqa_lr(args.data_dir)
    all_active = load_active_test_examples(
        images_path=args.data_dir / "LR_split_test_images.json",
        questions_path=args.data_dir / "LR_split_test_questions.json",
        answers_path=args.data_dir / "LR_split_test_answers.json",
    )
    validate_active_counts(all_active)  # aborts loudly if the real counts drifted
    active_image_count = len({example.image_id for example in all_active})
    print(
        f"Active RSVQA-LR test examples verified: "
        f"{active_image_count} images, {len(all_active)} questions"
    )

    examples = select_subset(all_active, size=args.slice_size, seed=args.seed)
    is_full_active_slice = len(examples) == len(all_active)
    run_label = (
        "full active slice, AC2 run"
        if is_full_active_slice
        else f"diagnostic subset, seed={args.seed}"
    )
    print(f"Evaluating {len(examples)} examples ({run_label})")

    model, tokenizer = load_model_and_tokenizer(args.adapter_path)
    transform = build_transform(IMAGE_SIZE)
    images_dir = args.data_dir / "Images_LR"

    predictions: list[Prediction] = []
    started = time.time()
    for i, example in enumerate(examples):
        image = Image.open(images_dir / example.image_filename)
        model_output = generate_answer(
            model=model,
            tokenizer=tokenizer,
            image=image,
            prompt=build_prompt(example),
            transform=transform,
        )
        predictions.append(
            Prediction(
                question_id=example.question_id,
                question_type=example.question_type,
                ground_truth=example.ground_truth,
                model_output=model_output,
            )
        )
        if (i + 1) % 50 == 0 or i + 1 == len(examples):
            elapsed = time.time() - started
            print(f"  {i + 1}/{len(examples)} ({elapsed:.1f}s elapsed)")

    score = score_predictions(predictions)
    print(f"Overall accuracy: {score.overall_accuracy:.4f} ({score.num_correct}/{score.num_total})")
    print(f"By type: {score.accuracy_by_type}")

    write_results(
        output_path=args.results_path,
        slice_size=len(examples),
        is_full_active_slice=is_full_active_slice,
        active_image_count=active_image_count,
        active_question_count=len(all_active),
        subset_seed=args.seed,
        score=score,
        model_id=MODEL_ID,
        adapter_path=args.adapter_path,
        adapter_commit=get_git_commit_hash(),
    )
    print(f"Results written: {args.results_path}")


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
