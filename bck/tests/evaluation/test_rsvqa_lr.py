"""Unit tests for app.evaluation.rsvqa_lr — synthetic fixtures, no network, no GPU.

Fixture shape mirrors the REAL official RSVQA-LR split files, verified live against
https://zenodo.org/records/6344334: every id in the full dataset appears in each
split file, but only active:true rows carry real question/answer/image data.
"""

import json
from pathlib import Path

import pytest

from app.evaluation.rsvqa_lr import (
    build_prompt,
    load_active_test_examples,
    select_subset,
    validate_active_counts,
)


def _write_split_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    images = {
        "images": [
            {"id": 0, "active": False},
            {"id": 1, "type": "RGB", "questions_ids": [10, 11], "active": True},
            {"id": 2, "type": "RGB", "questions_ids": [12], "active": True},
        ]
    }
    questions = {
        "questions": [
            {"id": 9, "active": False},
            {
                "id": 10,
                "img_id": 1,
                "type": "presence",
                "question": "Is there a road?",
                "answers_ids": [10],
                "active": True,
            },
            {
                "id": 11,
                "img_id": 1,
                "type": "count",
                "question": "How many buildings are present?",
                "answers_ids": [11],
                "active": True,
            },
            {
                "id": 12,
                "img_id": 2,
                "type": "rural_urban",
                "question": "Is it a rural or an urban area",
                "answers_ids": [12],
                "active": True,
            },
        ]
    }
    answers = {
        "answers": [
            {"id": 9, "active": False},
            {"id": 10, "question_id": 10, "answer": "yes", "active": True},
            {"id": 11, "question_id": 11, "answer": "3", "active": True},
            {"id": 12, "question_id": 12, "answer": "urban", "active": True},
        ]
    }

    images_path = tmp_path / "LR_split_test_images.json"
    questions_path = tmp_path / "LR_split_test_questions.json"
    answers_path = tmp_path / "LR_split_test_answers.json"
    images_path.write_text(json.dumps(images))
    questions_path.write_text(json.dumps(questions))
    answers_path.write_text(json.dumps(answers))
    return images_path, questions_path, answers_path


def test_load_active_test_examples_ignores_inactive_stub_rows(tmp_path: Path) -> None:
    """Inactive rows (real RSVQA-LR files are ~70% inactive stubs) must never surface."""
    images_path, questions_path, answers_path = _write_split_files(tmp_path)

    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )

    assert len(examples) == 3
    assert [e.question_id for e in examples] == [10, 11, 12]
    first = examples[0]
    assert first.image_id == 1
    assert first.image_filename == "1.tif"
    assert first.question == "Is there a road?"
    assert first.question_type == "presence"
    assert first.ground_truth == "yes"


def test_load_active_test_examples_raises_on_orphaned_active_question(tmp_path: Path) -> None:
    """An active question referencing an inactive/missing image or answer must be loud,
    not silently dropped (would understate the real slice size)."""
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    payload = json.loads(questions_path.read_text())
    payload["questions"].append(
        {"id": 99, "img_id": 999, "type": "presence", "question": "Orphan?", "active": True}
    )
    questions_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="99"):
        load_active_test_examples(
            images_path=images_path, questions_path=questions_path, answers_path=answers_path
        )


def test_select_subset_is_deterministic_for_a_fixed_seed(tmp_path: Path) -> None:
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )

    first = select_subset(examples, size=2, seed=7)
    second = select_subset(examples, size=2, seed=7)

    assert [e.question_id for e in first] == [e.question_id for e in second]
    assert len(first) == 2
    assert first != examples  # actually a subset, not the full list


def test_select_subset_returns_all_when_size_exceeds_available(tmp_path: Path) -> None:
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )

    subset = select_subset(examples, size=1000, seed=1)

    assert len(subset) == len(examples)


def test_select_subset_rejects_non_positive_size(tmp_path: Path) -> None:
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )
    with pytest.raises(ValueError):
        select_subset(examples, size=0, seed=1)


def test_validate_active_counts_passes_when_counts_match_expectation(tmp_path: Path) -> None:
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )
    validate_active_counts(examples, expected_images=2, expected_questions=3)


def test_validate_active_counts_raises_with_actual_numbers_on_mismatch(tmp_path: Path) -> None:
    """Must stop loudly and report the real counts found -- never a silent fallback
    to the invented/expected 10004/100 when the real data doesn't match."""
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )

    expected_message = r"expected 100 images / 10004 questions.*found 2 images / 3 questions"
    with pytest.raises(RuntimeError, match=expected_message):
        validate_active_counts(examples)


def test_build_prompt_matches_internvl_chat_format(tmp_path: Path) -> None:
    images_path, questions_path, answers_path = _write_split_files(tmp_path)
    examples = load_active_test_examples(
        images_path=images_path, questions_path=questions_path, answers_path=answers_path
    )
    assert build_prompt(examples[0]) == "<image>\nIs there a road?\nAnswer with a single word or number."
