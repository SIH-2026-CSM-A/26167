"""Pure accuracy scoring: predictions vs. ground truth, no model/GPU involved.

Deliberately separated from model inference (YASH-007 AC5) so this logic gets fast,
GPU-free unit tests.

presence / rural_urban / comp answers (verified live against the real test-split
answers: yes/no or rural/urban) are scored by exact string match after light
normalization. count answers are scored by the RSVQA paper's own bucketed-range
convention, not raw exact match: predicted and true counts are each bucketed into
one of [0, 1-10, 11-100, 101-1000, >1000] before comparing -- these boundaries were
given, not invented here.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.evaluation.schemas import Prediction, ScoreResult

COUNT_QUESTION_TYPE = "count"

_LEADING_INT_PATTERN = re.compile(r"-?\d+")


def normalize_answer(text: str) -> str:
    """Lowercase, strip whitespace, and strip trailing sentence punctuation."""
    return text.strip().lower().rstrip(".!? ")


def parse_count(text: str) -> int | None:
    """Extract the first integer in free-form model output, or None if there isn't one."""
    match = _LEADING_INT_PATTERN.search(text)
    return int(match.group()) if match else None


def bucket_count(value: int) -> str:
    """RSVQA paper's count-answer buckets: 0, 1-10, 11-100, 101-1000, >1000."""
    if value < 0:
        raise ValueError(f"count must be non-negative, got {value}")
    if value == 0:
        return "0"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "11-100"
    if value <= 1000:
        return "101-1000"
    return ">1000"


def is_correct(prediction: Prediction) -> bool:
    """Exact match for closed-vocabulary types; bucketed-range match for count."""
    if prediction.question_type == COUNT_QUESTION_TYPE:
        predicted = parse_count(prediction.model_output)
        truth = parse_count(prediction.ground_truth)
        if predicted is None or truth is None:
            return False
        return bucket_count(predicted) == bucket_count(truth)
    return normalize_answer(prediction.model_output) == normalize_answer(prediction.ground_truth)


def score_predictions(predictions: Sequence[Prediction]) -> ScoreResult:
    """Compute overall and per-type accuracy over a non-empty sequence of predictions."""
    if not predictions:
        raise ValueError("predictions must be non-empty")

    correct_by_type: dict[str, int] = {}
    total_by_type: dict[str, int] = {}
    num_correct = 0
    for prediction in predictions:
        correct = is_correct(prediction)
        num_correct += int(correct)
        total_by_type[prediction.question_type] = total_by_type.get(prediction.question_type, 0) + 1
        if correct:
            correct_by_type[prediction.question_type] = (
                correct_by_type.get(prediction.question_type, 0) + 1
            )

    accuracy_by_type = {
        question_type: correct_by_type.get(question_type, 0) / total
        for question_type, total in total_by_type.items()
    }

    return ScoreResult(
        overall_accuracy=num_correct / len(predictions),
        num_correct=num_correct,
        num_total=len(predictions),
        accuracy_by_type=accuracy_by_type,
        count_by_type=total_by_type,
    )
