"""Canonical evidence construction tests."""

import pytest

from app.contracts import EvidenceType, ImageInput, Modality
from app.evidence import build_bbox_evidence, build_vqa_evidence


def test_vqa_evidence_contains_actual_asset_and_model_provenance() -> None:
    """Text evidence must retain the source asset, filename, model, and real outputs."""
    asset = ImageInput(
        id="asset-1",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="scene.tif",
        metadata={"filename": "scene.tif", "width": 4, "height": 3},
    )

    evidence = build_vqa_evidence(
        asset=asset,
        model_id="OpenGVLab/InternVL2-2B",
        raw_answer="A river is visible.",
        verified_answer="A river is visible.",
        supporting_observations=("A river is visible.",),
        rejected_claims=(),
        timing_seconds=1.25,
    )

    assert evidence.type is EvidenceType.TEXT
    assert evidence.tool == "internvl_vqa"
    assert evidence.confidence == 0.0
    assert evidence.payload["confidence_available"] is False
    assert evidence.payload["source_asset_id"] == "asset-1"
    assert evidence.payload["source_filename"] == "scene.tif"
    assert evidence.payload["model_id"] == "OpenGVLab/InternVL2-2B"
    assert evidence.payload["raw_model_answer"] == "A river is visible."


def _asset() -> ImageInput:
    return ImageInput(
        id="asset-1",
        modality=Modality.OPTICAL,
        format="GTiff",
        path="scene.tif",
        metadata={"filename": "scene.tif"},
    )


def test_bbox_evidence_native_source_is_honestly_labeled() -> None:
    """A model-produced box must be traceable to InternVL, not silently anonymized."""
    evidence = build_bbox_evidence(
        asset=_asset(),
        model_id="OpenGVLab/InternVL3-2B",
        bbox=[51, 102, 154, 205],
        label="flooded area",
        source="internvl_native",
        timing_seconds=0.8,
    )

    assert evidence.type is EvidenceType.BBOX
    assert evidence.tool == "internvl_vqa"
    assert evidence.payload["bbox"] == [51, 102, 154, 205]
    assert evidence.payload["label"] == "flooded area"
    assert evidence.payload["source"] == "internvl_native"
    assert evidence.payload["model_id"] == "OpenGVLab/InternVL3-2B"
    assert evidence.payload["source_asset_id"] == "asset-1"
    assert evidence.confidence == 0.75


def test_bbox_evidence_otsu_fallback_is_not_presented_as_model_output() -> None:
    """A heuristic fallback box must never be reported under the model's identity."""
    evidence = build_bbox_evidence(
        asset=_asset(),
        model_id="OpenGVLab/InternVL3-2B",
        bbox=[0, 0, 385, 512],
        label="flooded area",
        source="otsu_fallback",
        timing_seconds=0.3,
    )

    assert evidence.tool == "otsu_fallback"
    assert evidence.payload["source"] == "otsu_fallback"
    assert evidence.payload["model_id"] is None
    assert evidence.confidence == 0.50
    assert evidence.confidence < 0.75  # strictly less trusted than a native box


def test_bbox_evidence_rejects_unknown_source() -> None:
    with pytest.raises(ValueError):
        build_bbox_evidence(
            asset=_asset(),
            model_id="OpenGVLab/InternVL3-2B",
            bbox=[0, 0, 10, 10],
            label="x",
            source="made_up",
            timing_seconds=0.1,
        )
