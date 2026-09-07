"""Tests for the CDVQA evaluation harness (app/eval/cdvqa.py).

Verifies:
a) Dataset parsing and split filtering (test1/test2).
b) Correct handling of question types and categories.
c) Accuracy calculation matching the paper's exact scoring metric.
d) End-to-end evaluation flow with a mocked pipeline forward pass.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.eval.cdvqa import (
    CHANGE_CATEGORIES,
    CDVQABitPipeline,
    CDVQAItem,
    compute_cdvqa_metrics,
    extract_change_category,
    load_cdvqa_dataset,
    normalize_answer,
    percentage_to_cdvqa_bin,
    run_cdvqa_eval,
)


def _create_dummy_image(path: Path, width: int = 512, height: int = 512, value: int = 128) -> None:
    """Create a deterministic 512x512 RGB PNG image."""
    arr = np.full((height, width, 3), fill_value=value, dtype=np.uint8)
    img = Image.fromarray(arr)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def _populate_synthetic_cdvqa_split(root_dir: Path, split: str = "test1") -> None:
    """Create synthetic JSON files and 512x512 images for a CDVQA split."""
    is_test2 = split.lower() == "test2"
    prefix = "Test2" if is_test2 else "Test"

    # Images
    images_payload = {
        "images": [
            {
                "id": 0,
                "res_x": ".1524m",
                "res_y": ".1524m",
                "questions_ids": [0, 1, 2, 3, 4],
                "file_name": "pair_001.png",
                "active": True,
            },
            {
                "id": 1,
                "res_x": ".1524m",
                "res_y": ".1524m",
                "questions_ids": [5, 6, 7, 8, 9, 10],
                "file_name": "pair_002.png",
                "active": True,
            },
            {
                "id": 2,
                "res_x": ".1524m",
                "res_y": ".1524m",
                "questions_ids": [99],
                "file_name": "pair_inactive.png",
                "active": False,
            },
        ]
    }

    # Questions covering the 8 types and 6 categories
    questions_payload = {
        "questions": [
            {
                "id": 0,
                "img_id": 0,
                "type": "change_or_not",
                "question": "Did the areas of non-vegetated ground surface change?",
                "answers_ids": [0],
                "active": True,
            },
            {
                "id": 1,
                "img_id": 0,
                "type": "change_or_not",
                "question": "Did the regions of buildings change?",
                "answers_ids": [1],
                "active": True,
            },
            {
                "id": 2,
                "img_id": 0,
                "type": "increase_or_not",
                "question": "Did the regions of playgrounds increase?",
                "answers_ids": [2],
                "active": True,
            },
            {
                "id": 3,
                "img_id": 0,
                "type": "decrease_or_not",
                "question": "Have the areas of water decreased?",
                "answers_ids": [3],
                "active": True,
            },
            {
                "id": 4,
                "img_id": 0,
                "type": "increase_or_not",
                "question": "Did the areas of low vegetation increase?",
                "answers_ids": [4],
                "active": True,
            },
            {
                "id": 5,
                "img_id": 1,
                "type": "change_or_not",
                "question": "Have the regions of trees changed?",
                "answers_ids": [5],
                "active": True,
            },
            {
                "id": 6,
                "img_id": 1,
                "type": "smallest_change",
                "question": "What type of change is the smallest?",
                "answers_ids": [6],
                "active": True,
            },
            {
                "id": 7,
                "img_id": 1,
                "type": "largest_change",
                "question": "What is the largest change?",
                "answers_ids": [7],
                "active": True,
            },
            {
                "id": 8,
                "img_id": 1,
                "type": "change_to_what",
                "question": "What have the areas of low vegetation mainly changed to?",
                "answers_ids": [8],
                "active": True,
            },
            {
                "id": 9,
                "img_id": 1,
                "type": "change_ratio",
                "question": "What is the percentage of changed regions?",
                "answers_ids": [9],
                "active": True,
            },
            {
                "id": 10,
                "img_id": 1,
                "type": "change_ratio_types",
                "question": "What is the change proportion of water in the second image?",
                "answers_ids": [10],
                "active": True,
            },
            {
                "id": 99,
                "img_id": 2,
                "type": "change_or_not",
                "question": "Did the trees change?",
                "answers_ids": [99],
                "active": False,
            },
        ]
    }

    # Answers
    answers_payload = {
        "answers": [
            {"id": 0, "question_id": 0, "answer": "yes", "active": True},
            {"id": 1, "question_id": 1, "answer": "yes", "active": True},
            {"id": 2, "question_id": 2, "answer": "no", "active": True},
            {"id": 3, "question_id": 3, "answer": "no", "active": True},
            {"id": 4, "question_id": 4, "answer": "no", "active": True},
            {"id": 5, "question_id": 5, "answer": "yes", "active": True},
            {"id": 6, "question_id": 6, "answer": "playgrounds", "active": True},
            {"id": 7, "question_id": 7, "answer": "buildings", "active": True},
            {"id": 8, "question_id": 8, "answer": "NVG_surface", "active": True},
            {"id": 9, "question_id": 9, "answer": "10_to_20", "active": True},
            {"id": 10, "question_id": 10, "answer": "0", "active": True},
            {"id": 99, "question_id": 99, "answer": "no", "active": False},
        ]
    }

    # Write JSON files
    with (root_dir / f"{prefix}_images.json").open("w", encoding="utf-8") as f:
        json.dump(images_payload, f)
    with (root_dir / f"{prefix}_questions.json").open("w", encoding="utf-8") as f:
        json.dump(questions_payload, f)
    with (root_dir / f"{prefix}_answers.json").open("w", encoding="utf-8") as f:
        json.dump(answers_payload, f)

    # Write dummy 512x512 bi-temporal images
    _create_dummy_image(root_dir / "im1" / "pair_001.png", value=50)
    _create_dummy_image(root_dir / "im2" / "pair_001.png", value=120)
    _create_dummy_image(root_dir / "im1" / "pair_002.png", value=80)
    _create_dummy_image(root_dir / "im2" / "pair_002.png", value=80)


def test_dataset_parsing_and_split_filtering(tmp_path: Path) -> None:
    """Test loading CDVQA annotations, split selection, and active item filtering."""
    _populate_synthetic_cdvqa_split(tmp_path, split="test1")
    _populate_synthetic_cdvqa_split(tmp_path, split="test2")

    # 1. Load test1
    items_test1 = load_cdvqa_dataset(tmp_path, split="test1", include_inactive=False)
    assert len(items_test1) == 11
    # Ensure inactive item (id=99) was filtered out
    assert all(item.question_id != 99 for item in items_test1)

    # 2. Include inactive
    items_all = load_cdvqa_dataset(tmp_path, split="test1", include_inactive=True)
    assert len(items_all) == 12

    # 3. Load test2
    items_test2 = load_cdvqa_dataset(tmp_path, split="test2")
    assert len(items_test2) == 11

    # 4. Limit testing
    items_limited = load_cdvqa_dataset(tmp_path, split="test1", limit=3)
    assert len(items_limited) == 3

    # 5. Invalid split raises FileNotFoundError
    with pytest.raises(FileNotFoundError, match="Could not find CDVQA"):
        load_cdvqa_dataset(tmp_path, split="invalid_split_name")


def test_question_types_and_category_extraction() -> None:
    """Verify correct classification of all 8 question types and 6 land-cover categories."""
    # Test all 6 categories extracted from question text
    assert (
        extract_change_category("Did the areas of non-vegetated ground surface change?")
        == "NVG_surface"
    )
    assert extract_change_category("Have the regions of buildings changed?") == "buildings"
    assert extract_change_category("Did the playgrounds area increase?") == "playgrounds"
    assert extract_change_category("Have the water regions decreased?") == "water"
    assert extract_change_category("Did the low vegetation change?") == "low_vegetation"
    assert extract_change_category("Have the trees grown?") == "trees"

    # Test category extracted from answer text when question is generic
    assert extract_change_category("What is the smallest change?", "playgrounds") == "playgrounds"
    assert extract_change_category("What is the largest change?", "buildings") == "buildings"
    assert (
        extract_change_category("What did low vegetation change to?", "NVG_surface")
        == "NVG_surface"
    )

    # Generic ratio questions have no specific single land-cover category
    assert extract_change_category("What is the percentage of changed regions?", "10_to_20") is None


def test_answer_normalization() -> None:
    """Test exact answer normalization logic against punctuation, aliases, and case."""
    # Binary yes/no
    assert normalize_answer("Yes.") == "yes"
    assert normalize_answer("yes") == "yes"
    assert normalize_answer("No, unchanged") == "no"
    assert normalize_answer("no.") == "no"

    # Category aliases
    assert normalize_answer("NVG surface") == "NVG_surface"
    assert normalize_answer("non-vegetated ground") == "NVG_surface"
    assert normalize_answer("Non-vegetated Ground Surface.") == "NVG_surface"
    assert normalize_answer("buildings") == "buildings"
    assert normalize_answer("building") == "buildings"
    assert normalize_answer("playgrounds") == "playgrounds"
    assert normalize_answer("low vegetation") == "low_vegetation"
    assert normalize_answer("trees.") == "trees"
    assert normalize_answer("water") == "water"

    # Ratio bin normalization
    assert normalize_answer("0 to 10%") == "0_to_10"
    assert normalize_answer("0-10") == "0_to_10"
    assert normalize_answer("10_to_20") == "10_to_20"
    assert normalize_answer("0%") == "0"
    assert normalize_answer("none") == "0"


def test_percentage_to_cdvqa_bin() -> None:
    """Verify numeric percentage mapping to CDVQA 10-percent bins."""
    assert percentage_to_cdvqa_bin(0.0) == "0"
    assert percentage_to_cdvqa_bin(0.0, has_change=False) == "0"
    assert percentage_to_cdvqa_bin(4.5, has_change=True) == "0_to_10"
    assert percentage_to_cdvqa_bin(15.0) == "10_to_20"
    assert percentage_to_cdvqa_bin(25.5) == "20_to_30"
    assert percentage_to_cdvqa_bin(32.1) == "30_to_40"
    assert percentage_to_cdvqa_bin(48.0) == "40_to_50"
    assert percentage_to_cdvqa_bin(55.2) == "50_to_60"
    assert percentage_to_cdvqa_bin(61.8) == "60_to_70"
    assert percentage_to_cdvqa_bin(79.9) == "70_to_80"
    assert percentage_to_cdvqa_bin(85.0) == "80_to_90"
    assert percentage_to_cdvqa_bin(99.4) == "90_to_100"


def test_accuracy_calculation_paper_metrics() -> None:
    """Test Overall Accuracy, Average Category Accuracy, and per-category scoring."""
    sample_items = [
        CDVQAItem(
            question_id=1,
            question="Q1",
            question_type="change_or_not",
            category="NVG_surface",
            ground_truth="yes",
            img_id=1,
            file_name="f1.png",
        ),
        CDVQAItem(
            question_id=2,
            question="Q2",
            question_type="change_or_not",
            category="buildings",
            ground_truth="no",
            img_id=1,
            file_name="f1.png",
        ),
        CDVQAItem(
            question_id=3,
            question="Q3",
            question_type="increase_or_not",
            category="playgrounds",
            ground_truth="yes",
            img_id=1,
            file_name="f1.png",
        ),
        CDVQAItem(
            question_id=4,
            question="Q4",
            question_type="decrease_or_not",
            category="water",
            ground_truth="no",
            img_id=1,
            file_name="f1.png",
        ),
        CDVQAItem(
            question_id=5,
            question="Q5",
            question_type="change_or_not",
            category="low_vegetation",
            ground_truth="yes",
            img_id=1,
            file_name="f1.png",
        ),
        CDVQAItem(
            question_id=6,
            question="Q6",
            question_type="change_or_not",
            category="trees",
            ground_truth="no",
            img_id=1,
            file_name="f1.png",
        ),
    ]

    # Predictions: 5 correct, 1 wrong (trees is predicted as 'yes' instead of 'no')
    predictions = ["yes", "no", "yes", "no", "yes", "yes"]

    result = compute_cdvqa_metrics(eval_items=sample_items, predictions=predictions, split="test1")

    # Overall accuracy: 5 / 6 = 83.33%
    assert result.total_questions == 6
    assert result.total_correct == 5
    assert result.overall_accuracy == 83.33

    # All 6 categories must be present in per_category_accuracy
    for cat in CHANGE_CATEGORIES:
        assert cat in result.per_category_accuracy

    assert result.per_category_accuracy["NVG_surface"].accuracy == 100.0
    assert result.per_category_accuracy["buildings"].accuracy == 100.0
    assert result.per_category_accuracy["playgrounds"].accuracy == 100.0
    assert result.per_category_accuracy["water"].accuracy == 100.0
    assert result.per_category_accuracy["low_vegetation"].accuracy == 100.0
    assert result.per_category_accuracy["trees"].accuracy == 0.0

    # Average Category Accuracy = (100 + 100 + 100 + 100 + 100 + 0) / 6 = 83.33%
    assert result.average_category_accuracy == 83.33

    # Per-type metrics
    assert "change_or_not" in result.per_type_accuracy
    # 4 change_or_not items (NVG, buildings, low_veg, trees): 3 correct, 1 wrong -> 75%
    assert result.per_type_accuracy["change_or_not"].total == 4
    assert result.per_type_accuracy["change_or_not"].correct == 3
    assert result.per_type_accuracy["change_or_not"].accuracy == 75.0


def test_e2e_evaluation_flow_with_mocked_pipeline(tmp_path: Path) -> None:
    """Run full end-to-end evaluation harness with a mocked pipeline forward pass."""
    _populate_synthetic_cdvqa_split(tmp_path, split="test1")
    output_json = tmp_path / "artifacts" / "test1_eval_results.json"

    # Mock pipeline returning exact ground-truth or deterministic response
    def mocked_pipeline(
        image_a_path: str | None,
        image_b_path: str | None,
        question: str,
        question_type: str | None,
        category: str | None,
    ) -> str:
        # Check bi-temporal images exist and are 512x512
        if image_a_path and image_b_path:
            with Image.open(image_a_path) as img_a:
                assert img_a.size == (512, 512)
            with Image.open(image_b_path) as img_b:
                assert img_b.size == (512, 512)

        if question_type == "change_or_not":
            return "yes"
        if question_type == "increase_or_not":
            return "no"
        if question_type == "decrease_or_not":
            return "no"
        if question_type == "smallest_change":
            return "playgrounds"
        if question_type == "largest_change":
            return "buildings"
        if question_type == "change_to_what":
            return "NVG_surface"
        if question_type == "change_ratio":
            return "10_to_20"
        if question_type == "change_ratio_types":
            return "0"
        return "yes"

    results = run_cdvqa_eval(
        split="test1",
        data_dir=tmp_path,
        output_json=output_json,
        device="cpu",
        pipeline=mocked_pipeline,
        detailed=True,
    )

    # 1. Output structure assertions
    assert results["benchmark"] == "CDVQA"
    assert results["dataset_source"] == "https://github.com/YZHJessica/CDVQA"
    assert results["license"] == "Apache-2.0"
    assert results["split"] == "test1"
    assert results["total_questions"] == 11
    assert results["total_correct"] == 11
    assert results["overall_accuracy"] == 100.0
    assert results["average_category_accuracy"] == 100.0

    # 2. Per-category metrics contain all 6 land-cover categories
    for cat in CHANGE_CATEGORIES:
        assert cat in results["per_category_accuracy"]
        metric = results["per_category_accuracy"][cat]
        assert "correct" in metric and "total" in metric and "accuracy" in metric

    # 3. JSON artifact was saved and is valid
    assert output_json.is_file()
    with output_json.open("r", encoding="utf-8") as f:
        loaded_json = json.load(f)
    assert loaded_json["overall_accuracy"] == 100.0
    assert len(loaded_json["detailed_results"]) == 11


def test_wired_cdvqa_bit_pipeline_with_dummy_images(tmp_path: Path) -> None:
    """Verify wired CDVQABitPipeline produces grounded answers from image pairs."""
    img_a_path = tmp_path / "a.png"
    img_b_path = tmp_path / "b.png"

    # Pair with real pixel difference
    arr_a = np.zeros((512, 512, 3), dtype=np.uint8)
    arr_b = np.zeros((512, 512, 3), dtype=np.uint8)
    # 25% changed patch
    arr_b[100:356, 100:356, :] = 200

    Image.fromarray(arr_a).save(img_a_path)
    Image.fromarray(arr_b).save(img_b_path)

    pipeline = CDVQABitPipeline(checkpoint_path=None, device="cpu")

    # 1. Change or not
    pred_change = pipeline.predict(
        image_a_path=str(img_a_path),
        image_b_path=str(img_b_path),
        question="Did the scene change?",
        question_type="change_or_not",
    )
    assert pred_change == "yes"

    # 2. Ratio should fall into 20_to_30 (changed patch is ~24.4% of 512x512)
    pred_ratio = pipeline.predict(
        image_a_path=str(img_a_path),
        image_b_path=str(img_b_path),
        question="What is the percentage of changed regions?",
        question_type="change_ratio",
    )
    assert pred_ratio == "20_to_30"

    # 3. Identical images -> no change
    pred_no_change = pipeline.predict(
        image_a_path=str(img_a_path),
        image_b_path=str(img_a_path),
        question="Did the scene change?",
        question_type="change_or_not",
    )
    assert pred_no_change == "no"


def test_evaluation_performance_and_determinism(tmp_path: Path) -> None:
    """Ensure evaluation is CPU-friendly, fast (< 5 seconds), and deterministic."""
    _populate_synthetic_cdvqa_split(tmp_path, split="test1")

    pipeline = CDVQABitPipeline(checkpoint_path=None, device="cpu")

    t0 = time.perf_counter()
    run1 = run_cdvqa_eval(split="test1", data_dir=tmp_path, output_json=None, pipeline=pipeline)
    run2 = run_cdvqa_eval(split="test1", data_dir=tmp_path, output_json=None, pipeline=pipeline)
    elapsed = time.perf_counter() - t0

    # Must be fast (< 5 seconds)
    assert elapsed < 5.0

    # Must be completely deterministic
    assert run1["overall_accuracy"] == run2["overall_accuracy"]
    assert run1["total_correct"] == run2["total_correct"]
    assert run1["per_category_accuracy"] == run2["per_category_accuracy"]
