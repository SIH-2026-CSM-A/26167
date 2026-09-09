"""Regression coverage for JSON-safe specialist evidence responses."""

import numpy as np

from app.contracts import Evidence, EvidenceType
from app.pipeline.pipeline import _json_safe_evidence


def test_numpy_mask_evidence_is_json_native_at_response_boundary() -> None:
    """Mask arrays are converted before FastAPI serializes the Answer response."""
    evidence = Evidence(
        id="mask",
        tool="fusion.reconcile",
        type=EvidenceType.MASK,
        payload={"water_mask": np.array([[True, False]])},
        confidence=1.0,
        timing=0.1,
    )

    safe = _json_safe_evidence([evidence])[0]

    assert safe.payload == {"water_mask": [[True, False]]}
