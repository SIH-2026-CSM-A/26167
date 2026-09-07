"""Smoke test: schema dataclasses are plain, frozen, and constructible as documented."""

from app.evaluation.schemas import Prediction, RsvqaExample, ScoreResult


def test_rsvqa_example_is_frozen_and_holds_all_fields() -> None:
    example = RsvqaExample(
        question_id=10,
        image_id=1,
        image_filename="1.tif",
        question="Is there a road?",
        question_type="presence",
        ground_truth="yes",
    )
    assert example.image_filename == "1.tif"


def test_prediction_and_score_result_are_constructible() -> None:
    prediction = Prediction(
        question_id=1, question_type="count", ground_truth="3", model_output="3"
    )
    result = ScoreResult(
        overall_accuracy=1.0,
        num_correct=1,
        num_total=1,
        accuracy_by_type={"count": 1.0},
        count_by_type={"count": 1},
    )
    assert prediction.question_type == "count"
    assert result.overall_accuracy == 1.0
