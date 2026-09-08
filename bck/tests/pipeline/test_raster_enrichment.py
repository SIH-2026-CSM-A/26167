"""Regression tests for shared BIT and fusion raster enrichment."""

import numpy as np

from app.contracts import Evidence, EvidenceType
from app.pipeline.pipeline import _enrich_mask_evidence


def test_change_and_water_masks_share_titiler_enrichment(monkeypatch) -> None:
    """Both specialist mask payload names produce the same raster URL contract."""
    evidences = [
        Evidence(
            id="change",
            tool="change_detection.bit",
            type=EvidenceType.MASK,
            payload={"change_mask": np.ones((2, 2), dtype=bool)},
            confidence=1.0,
            timing=0.1,
        ),
        Evidence(
            id="water",
            tool="fusion.reconcile",
            type=EvidenceType.MASK,
            payload={"water_mask": np.ones((2, 2), dtype=bool)},
            confidence=1.0,
            timing=0.1,
        ),
    ]
    monkeypatch.setattr(
        "app.pipeline.pipeline.write_mask_artifact",
        lambda mask, source: f"http://127.0.0.1:8001/cog/tiles/{{z}}/{{x}}/{{y}}?url={id(mask)}",
    )

    enriched = _enrich_mask_evidence(evidences, object())

    assert all("raster_url" in evidence.payload for evidence in enriched)
