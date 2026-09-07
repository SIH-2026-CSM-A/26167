"""Plain dataclass schema types for the standalone evaluation harness.

Deliberately separate from app.contracts: those are the running application's
request/response/evidence contracts, and this harness must not be coupled to (or
constrained by) the running application's schema evolution -- see the package
docstring in app/evaluation/__init__.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RsvqaExample:
    """One active RSVQA-LR test-split question, joined against its image and answer."""

    question_id: int
    image_id: int
    image_filename: str
    question: str
    question_type: str
    ground_truth: str


@dataclass(frozen=True, slots=True)
class Prediction:
    """One scored (model output, ground truth) pair, keeping its question type."""

    question_id: int
    question_type: str
    ground_truth: str
    model_output: str


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """Overall and per-question-type accuracy over a set of predictions."""

    overall_accuracy: float
    num_correct: int
    num_total: int
    accuracy_by_type: dict[str, float]
    count_by_type: dict[str, int]
