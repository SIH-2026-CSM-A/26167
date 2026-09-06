"""Canonical evidence construction tests."""

from app.contracts import EvidenceType, ImageInput, Modality
from app.evidence import build_vqa_evidence


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
