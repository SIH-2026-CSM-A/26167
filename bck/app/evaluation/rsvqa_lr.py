"""RSVQA-LR benchmark loading: parse the official Zenodo split JSON files.

Official source: Zenodo record 6344334 (concept DOI 10.5281/zenodo.6344333 redirects
here) -- Images_LR.zip, LR_split_test_images.json, LR_split_test_questions.json,
LR_split_test_answers.json.

Real structure, verified live against the actual downloaded files -- not assumed:
each `LR_split_test_*.json` file lists every id in the FULL 772-image / 77,232-QA
dataset, not just that split's entries. An entry belongs to this split only when its
own `"active"` flag is true; inactive entries are placeholder stubs carrying nothing
but `{"id": ..., "active": false}` -- no question/answer/image data at all. The real
RSVQA-LR test split is therefore the *active* subset: 100 images and 10,004
question/answer pairs. Images on disk inside Images_LR.zip are named by plain
numeric id (`{img_id}.tif`, e.g. "232.tif"), not `original_name`.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from app.evaluation.schemas import RsvqaExample

_IMAGE_CONTEXT_TAG = "<image>"

EXPECTED_ACTIVE_IMAGE_COUNT = 100
EXPECTED_ACTIVE_QUESTION_COUNT = 10004


def load_active_test_examples(
    *,
    images_path: Path,
    questions_path: Path,
    answers_path: Path,
) -> list[RsvqaExample]:
    """Join the three official split files, keeping only active (real test-split) rows.

    Raises ValueError if an active question has no matching active image or answer --
    the official files are expected to be internally consistent; silently skipping a
    mismatch would understate the slice size without saying so.
    """
    images = _active_rows_by_id(images_path, "images")
    questions = _active_rows_by_id(questions_path, "questions")
    answers = _active_rows_by_id(answers_path, "answers")

    answer_by_question_id: dict[int, dict] = {}
    for answer in answers.values():
        answer_by_question_id.setdefault(answer["question_id"], answer)

    examples: list[RsvqaExample] = []
    for question in questions.values():
        image = images.get(question["img_id"])
        answer = answer_by_question_id.get(question["id"])
        if image is None or answer is None:
            raise ValueError(
                f"active question {question['id']} has no matching active image/answer "
                "in the official RSVQA-LR test split files"
            )
        examples.append(
            RsvqaExample(
                question_id=question["id"],
                image_id=image["id"],
                image_filename=f"{image['id']}.tif",
                question=question["question"],
                question_type=question["type"],
                ground_truth=answer["answer"],
            )
        )

    examples.sort(key=lambda example: example.question_id)
    return examples


def validate_active_counts(
    examples: list[RsvqaExample],
    *,
    expected_images: int = EXPECTED_ACTIVE_IMAGE_COUNT,
    expected_questions: int = EXPECTED_ACTIVE_QUESTION_COUNT,
) -> None:
    """Refuse to proceed if the real active-record counts don't match what was verified.

    AC2 requires reporting the exact real slice size, never an invented or rounded
    one. If Zenodo's files ever change, or a parsing bug creeps in, this must halt
    loudly with the actual counts found instead of letting a wrong number reach the
    results JSON.
    """
    actual_images = len({example.image_id for example in examples})
    actual_questions = len(examples)
    if actual_images != expected_images or actual_questions != expected_questions:
        raise RuntimeError(
            "RSVQA-LR active-record counts do not match the verified expectation -- "
            f"expected {expected_images} images / {expected_questions} questions, "
            f"found {actual_images} images / {actual_questions} questions. "
            "Stopping rather than reporting a score against an unverified slice."
        )


def select_subset(
    examples: list[RsvqaExample], *, size: int | None, seed: int
) -> list[RsvqaExample]:
    """Fixed-seed subset of `examples`, or all of them if size is None or too large.

    A fixed seed makes the subset (and therefore the score) reproducible across runs
    against the same full example list. Only for quick, explicitly-labeled diagnostic
    runs -- AC2's real reported score must use the full active slice.
    """
    if size is None or size >= len(examples):
        return list(examples)
    if size <= 0:
        raise ValueError("size must be positive")
    return random.Random(seed).sample(examples, size)


def build_prompt(example: RsvqaExample) -> str:
    """Build InternVL's chat-format question text for one RSVQA-LR example."""
    return f"{_IMAGE_CONTEXT_TAG}\n{example.question}"


def _active_rows_by_id(path: Path, list_key: str) -> dict[int, dict]:
    payload = json.loads(Path(path).read_text())
    return {row["id"]: row for row in payload[list_key] if row.get("active")}
