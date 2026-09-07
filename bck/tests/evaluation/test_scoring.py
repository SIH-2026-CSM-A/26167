"""Unit tests for app.evaluation.scoring — pure logic, no GPU, no network."""

import pytest

from app.evaluation.schemas import Prediction
from app.evaluation.scoring import (
    bucket_count,
    is_correct,
    normalize_answer,
    parse_count,
    score_predictions,
)


def test_normalize_answer_strips_case_whitespace_and_trailing_punctuation() -> None:
    assert normalize_answer("  Urban.  ") == "urban"
    assert normalize_answer("Yes!") == "yes"
    assert normalize_answer("3") == "3"


def test_parse_count_extracts_leading_integer_from_free_text() -> None:
    assert parse_count("3") == 3
    assert parse_count("There are 42 buildings.") == 42
    assert parse_count("no idea") is None


@pytest.mark.parametrize(
    "value, expected_bucket",
    [
        (0, "0"),
        (1, "1-10"),
        (10, "1-10"),
        (11, "11-100"),
        (100, "11-100"),
        (101, "101-1000"),
        (1000, "101-1000"),
        (1001, ">1000"),
    ],
)
def test_bucket_count_matches_rsvqa_paper_boundaries(value: int, expected_bucket: str) -> None:
    assert bucket_count(value) == expected_bucket


def test_bucket_count_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        bucket_count(-1)


def test_is_correct_buckets_count_answers_instead_of_exact_matching() -> None:
    """7 predicted vs. 9 true are both in the 1-10 bucket -> correct, though not equal."""
    prediction = Prediction(
        question_id=1, question_type="count", ground_truth="9", model_output="7"
    )
    assert is_correct(prediction) is True


def test_is_correct_rejects_count_answers_in_different_buckets() -> None:
    prediction = Prediction(
        question_id=1, question_type="count", ground_truth="9", model_output="15"
    )
    assert is_correct(prediction) is False


def test_is_correct_treats_unparseable_count_output_as_incorrect() -> None:
    prediction = Prediction(
        question_id=1, question_type="count", ground_truth="9", model_output="lots"
    )
    assert is_correct(prediction) is False


def test_score_predictions_computes_overall_and_per_type_accuracy() -> None:
    predictions = [
        Prediction(
            question_id=1, question_type="presence", ground_truth="yes", model_output="Yes."
        ),
        Prediction(question_id=2, question_type="presence", ground_truth="no", model_output="yes"),
        Prediction(question_id=3, question_type="count", ground_truth="3", model_output="3"),
        Prediction(question_id=4, question_type="count", ground_truth="0", model_output="150"),
    ]

    result = score_predictions(predictions)

    assert result.num_total == 4
    assert result.num_correct == 2
    assert result.overall_accuracy == pytest.approx(0.5)
    assert result.accuracy_by_type == {"presence": pytest.approx(0.5), "count": pytest.approx(0.5)}
    assert result.count_by_type == {"presence": 2, "count": 2}


def test_score_predictions_all_correct_is_1_0() -> None:
    predictions = [
        Prediction(
            question_id=1, question_type="rural_urban", ground_truth="rural", model_output="rural"
        ),
    ]
    result = score_predictions(predictions)
    assert result.overall_accuracy == 1.0
    assert result.num_correct == 1


def test_score_predictions_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        score_predictions([])
