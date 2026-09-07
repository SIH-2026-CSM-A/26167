"""Unit tests for VRSBench evaluation harness (app.eval.vrsbench_eval)."""

from app.eval.vrsbench_eval import (
    _rate,
    aggregate_referring,
    aggregate_vqa,
    iou_xyxy,
    normalize_answer,
    parse_vrsbench_box,
    vrsbench_box_to_pixels,
)


def test_iou_xyxy():
    # Exact match
    assert iou_xyxy([0.0, 0.0, 10.0, 10.0], [0.0, 0.0, 10.0, 10.0]) == 1.0

    # No intersection
    assert iou_xyxy([0.0, 0.0, 5.0, 5.0], [10.0, 10.0, 15.0, 15.0]) == 0.0

    # Partial overlap (5x10 intersection area = 50, total union area = 150 -> 1/3)
    box_a = [0.0, 0.0, 10.0, 10.0]
    box_b = [5.0, 0.0, 15.0, 10.0]
    assert abs(iou_xyxy(box_a, box_b) - 50.0 / 150.0) < 1e-5

    # Degenerate invalid box
    assert iou_xyxy([10.0, 10.0, 5.0, 5.0], [0.0, 0.0, 10.0, 10.0]) == 0.0


def test_normalize_answer():
    assert normalize_answer("  Yes.  ") == "yes"
    assert normalize_answer("Two airplanes, parked.") == "two airplanes parked"
    assert normalize_answer("A building with a roof.") == "a building with a roof"


def test_parse_vrsbench_box():
    # Typical VRSBench ground truth formats
    assert parse_vrsbench_box("[10, 20, 30, 40]") == [10, 20, 30, 40]
    assert parse_vrsbench_box("10, 20, 30, 40") == [10, 20, 30, 40]
    assert parse_vrsbench_box("invalid format") is None
    assert parse_vrsbench_box("") is None


def test_vrsbench_box_to_pixels():
    # Assuming VRSBench normalized 0-100 range box mapped to width=200, height=100
    box_0_100 = [10, 20, 50, 80]
    pixels = vrsbench_box_to_pixels(box_0_100, width=200, height=100)
    assert pixels == [20.0, 20.0, 100.0, 80.0]


def test_rate():
    assert _rate(1, 2) == 0.5
    assert _rate(0, 5) == 0.0
    assert _rate(5, 0) is None


def test_aggregate_vqa():
    records = [
        {
            "exact_match": True,
            "normalized_match": True,
            "bbox_pass_fired": True,
            "bbox_pass_returned_box": True,
            "error": None,
        },
        {
            "exact_match": False,
            "normalized_match": True,
            "bbox_pass_fired": False,
            "bbox_pass_returned_box": False,
            "error": None,
        },
        {
            "exact_match": False,
            "normalized_match": False,
            "bbox_pass_fired": False,
            "bbox_pass_returned_box": False,
            "error": "TimeoutError",
        },
    ]
    summary = aggregate_vqa(records)
    assert summary["items_evaluated"] == 3
    assert summary["items_errored"] == 1
    assert summary["accuracy_exact_match"] == 0.5
    assert summary["accuracy_normalized_match"] == 1.0


def test_aggregate_referring():
    records = [
        {
            "trigger_fired": True,
            "returned_box": True,
            "iou": 0.8,
            "error": None,
        },
        {
            "trigger_fired": True,
            "returned_box": False,
            "iou": 0.0,
            "error": None,
        },
        {
            "trigger_fired": False,
            "returned_box": False,
            "iou": None,
            "error": "ExecutionError",
        },
    ]
    summary = aggregate_referring(records)
    assert summary["items_evaluated"] == 3
    assert summary["items_errored"] == 1
    assert summary["returned_box_count"] == 1
    assert summary["localization_acc_iou_0.5"] == 0.5
