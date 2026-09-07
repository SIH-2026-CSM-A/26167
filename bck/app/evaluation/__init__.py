"""Standalone benchmark evaluation harness (YASH-007, AC2 / RSVQA-LR only).

Deliberately does not import from app.pipeline, app.contracts, app.api, or any
other application module -- this package is not wired into the running app; it is
invoked manually via bck/scripts/run_benchmarks.py.

AC1 (BigEarthNet.txt manually-verified benchmark split) is out of scope here and
owned by ROHAN-008 -- do not add BigEarthNet.txt code to this package.
"""

from app.evaluation.results import DOMAIN_MISMATCH_NOTE, SCOPE_NOTE, write_results
from app.evaluation.rsvqa_lr import (
    EXPECTED_ACTIVE_IMAGE_COUNT,
    EXPECTED_ACTIVE_QUESTION_COUNT,
    build_prompt,
    load_active_test_examples,
    select_subset,
    validate_active_counts,
)
from app.evaluation.schemas import Prediction, RsvqaExample, ScoreResult
from app.evaluation.scoring import (
    bucket_count,
    is_correct,
    normalize_answer,
    parse_count,
    score_predictions,
)

__all__ = [
    "DOMAIN_MISMATCH_NOTE",
    "EXPECTED_ACTIVE_IMAGE_COUNT",
    "EXPECTED_ACTIVE_QUESTION_COUNT",
    "Prediction",
    "RsvqaExample",
    "SCOPE_NOTE",
    "ScoreResult",
    "bucket_count",
    "build_prompt",
    "is_correct",
    "load_active_test_examples",
    "normalize_answer",
    "parse_count",
    "score_predictions",
    "select_subset",
    "validate_active_counts",
    "write_results",
]
