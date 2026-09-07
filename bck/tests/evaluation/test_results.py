"""Unit tests for app.evaluation.results — pure file I/O, no GPU, no network."""

import json
from pathlib import Path

import pytest

from app.evaluation.results import DOMAIN_MISMATCH_NOTE, SCOPE_NOTE, write_results
from app.evaluation.schemas import Prediction
from app.evaluation.scoring import score_predictions


def _score():
    predictions = [
        Prediction(question_id=1, question_type="presence", ground_truth="yes", model_output="yes"),
        Prediction(question_id=2, question_type="presence", ground_truth="no", model_output="yes"),
    ]
    return score_predictions(predictions)


def test_write_results_creates_parent_dir_and_expected_fields(tmp_path: Path) -> None:
    """Smoke test on the output JSON schema -- every field F23/the methodology
    section needs to cite must be present and correctly typed."""
    output_path = tmp_path / "results" / "rsvqa_lr.json"
    score = _score()

    write_results(
        output_path=output_path,
        slice_size=2,
        is_full_active_slice=False,
        active_image_count=100,
        active_question_count=10004,
        subset_seed=42,
        score=score,
        model_id="OpenGVLab/InternVL3-2B",
        adapter_path="app/training/checkpoints/yash004_mlp1_vision_lora",
        adapter_commit="b60d9ae",
    )

    assert output_path.exists()
    payload = json.loads(output_path.read_text())
    assert payload["benchmark"] == "RSVQA-LR"
    assert payload["source"] == "https://zenodo.org/records/6344334"
    assert payload["slice_size"] == 2
    assert payload["is_full_active_slice"] is False
    assert payload["active_image_count"] == 100
    assert payload["active_question_count"] == 10004
    assert payload["subset_seed"] == 42
    assert payload["accuracy"] == pytest.approx(0.5)
    assert payload["num_correct"] == 1
    assert payload["num_total"] == 2
    assert isinstance(payload["accuracy_by_type"], dict)
    assert isinstance(payload["count_by_type"], dict)
    assert payload["model_id"] == "OpenGVLab/InternVL3-2B"
    assert payload["adapter_path"] == "app/training/checkpoints/yash004_mlp1_vision_lora"
    assert payload["adapter_commit"] == "b60d9ae"
    assert isinstance(payload["timestamp"], str) and payload["timestamp"]
    assert payload["domain_mismatch_note"] == DOMAIN_MISMATCH_NOTE
    assert "EuroSAT" in payload["domain_mismatch_note"]
    assert "Sentinel" in payload["domain_mismatch_note"]
    assert payload["scope_note"] == SCOPE_NOTE
    assert "ROHAN-008" in payload["scope_note"]


def test_write_results_accepts_missing_adapter_commit(tmp_path: Path) -> None:
    """A non-git deployment environment must still produce a valid results file."""
    output_path = tmp_path / "rsvqa_lr.json"
    score = _score()

    write_results(
        output_path=output_path,
        slice_size=2,
        is_full_active_slice=True,
        active_image_count=100,
        active_question_count=10004,
        subset_seed=42,
        score=score,
        model_id="OpenGVLab/InternVL3-2B",
        adapter_path="app/training/checkpoints/yash004_mlp1_vision_lora",
        adapter_commit=None,
    )

    payload = json.loads(output_path.read_text())
    assert payload["adapter_commit"] is None
    assert payload["is_full_active_slice"] is True


def test_write_results_rejects_mismatched_slice_size(tmp_path: Path) -> None:
    """The reported slice size must equal what was actually scored -- no invented count."""
    output_path = tmp_path / "rsvqa_lr.json"
    score = _score()

    with pytest.raises(ValueError):
        write_results(
            output_path=output_path,
            slice_size=999,
            is_full_active_slice=False,
            active_image_count=100,
            active_question_count=10004,
            subset_seed=42,
            score=score,
            model_id="OpenGVLab/InternVL3-2B",
            adapter_path="app/training/checkpoints/yash004_mlp1_vision_lora",
            adapter_commit="b60d9ae",
        )
