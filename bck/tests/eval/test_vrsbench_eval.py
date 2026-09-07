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

    # Partial overlap (5x10 intersection area = 50, union area = 150 -> 1/3)
    box_a = [0.0, 0.0, 10.0, 10.0]
    box_b = [5.0, 0.0, 15.0, 10.0]
    assert abs(iou_xyxy(box_a, box_b) - (50.0 / 150.0)) < 1e-5

    # Degenerate invalid box
    assert iou_xyxy([10.0, 10.0, 5.0, 5.0], [0.0, 0.0, 10.0, 10.0]) == 0.0


def test_normalize_answer():
    assert normalize_answer("  Yes.  ") == "yes"
    assert normalize_answer("Two airplanes, parked.") == "two airplanes parked"
    # Drops articles: 'a', 'an', 'the'
    assert normalize_answer("A building with a roof.") == "building with roof"
    assert normalize_answer("The plane and an airport") == "plane and airport"


def test_parse_vrsbench_box():
    # VRSBench coordinate string format expects <digit> tags
    assert parse_vrsbench_box("{<10><20><30><40>}") == [10, 20, 30, 40]
    assert parse_vrsbench_box("<5><15><25><35>") == [5, 15, 25, 35]
    # Invalid: lacks <digit> tags or has wrong count
    assert parse_vrsbench_box("10, 20, 30, 40") is None
    assert parse_vrsbench_box("{<10><20><30>}") is None
    assert parse_vrsbench_box("") is None


def test_vrsbench_box_to_pixels():
    # Normalized 0-100 scale to pixel coordinates
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
            "pred_answer": "building",
            "trigger_fired": True,
            "bbox_pred_px": [10.0, 10.0, 50.0, 50.0],
            "bbox_source": "internvl_native",
            "error": None,
        },
        {
            "exact_match": False,
            "normalized_match": True,
            "pred_answer": "trees",
            "trigger_fired": False,
            "bbox_pred_px": None,
            "bbox_source": None,
            "error": None,
        },
        {
            "exact_match": False,
            "normalized_match": False,
            "pred_answer": None,
            "trigger_fired": False,
            "bbox_pred_px": None,
            "bbox_source": None,
            "error": "TimeoutError",
        },
    ]
    summary = aggregate_vqa(records)
    assert summary["items_evaluated"] == 3
    assert summary["items_scored"] == 2
    assert summary["items_errored"] == 1
    assert summary["accuracy_exact_match"] == 0.5
    assert summary["accuracy_normalized_match"] == 1.0
    assert summary["bbox_trigger_fire_rate"] == 0.5
    assert summary["bbox_pass_returned_box_count"] == 1
    assert summary["bbox_source_breakdown"]["internvl_native"] == 1
    assert summary["bbox_source_breakdown"]["none"] == 1


def test_aggregate_referring():
    records = [
        {
            "trigger_fired": True,
            "bbox_pred_px": [10.0, 10.0, 50.0, 50.0],
            "bbox_source": "internvl_native",
            "iou": 0.8,
            "iou_at_0.5": True,
            "error": None,
        },
        {
            "trigger_fired": True,
            "bbox_pred_px": None,
            "bbox_source": None,
            "iou": 0.0,
            "iou_at_0.5": False,
            "error": None,
        },
        {
            "trigger_fired": False,
            "bbox_pred_px": None,
            "bbox_source": None,
            "iou": None,
            "iou_at_0.5": False,
            "error": "ExecutionError",
        },
    ]
    summary = aggregate_referring(records)
    assert summary["items_evaluated"] == 3
    assert summary["items_scored"] == 2
    assert summary["items_errored"] == 1
    assert summary["trigger_fire_rate"] == 1.0
    assert summary["returned_box_count"] == 1
    assert summary["returned_box_rate"] == 0.5
    assert summary["mean_iou_all"] == 0.4
    assert summary["mean_iou_over_returned"] == 0.8
    assert summary["localization_acc_iou_0.5"] == 0.5
    assert summary["localization_acc_iou_0.5_over_returned"] == 1.0
