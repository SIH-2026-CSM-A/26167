"""Canonical evidence and answer assembly from verified VQA execution facts."""

from __future__ import annotations

import uuid

from app.contracts import Answer, Evidence, EvidenceType, ExecutionTrace, ImageInput


def build_vqa_evidence(
    *,
    asset: ImageInput,
    model_id: str,
    raw_answer: str,
    verified_answer: str,
    supporting_observations: tuple[str, ...],
    rejected_claims: tuple[str, ...],
    timing_seconds: float,
) -> Evidence:
    """Create traceable text evidence without inventing unavailable confidence or geometry."""
    return Evidence(
        id=str(uuid.uuid4()),
        tool="internvl_vqa",
        type=EvidenceType.TEXT,
        payload={
            "source_asset_id": asset.id,
            "source_filename": asset.metadata.get("filename"),
            "source_format": asset.format,
            "source_metadata": dict(asset.metadata),
            "model_id": model_id,
            "raw_model_answer": raw_answer,
            "verified_answer": verified_answer,
            "supporting_observations": list(supporting_observations),
            "rejected_claims": list(rejected_claims),
            "confidence_available": False,
        },
        confidence=0.0,
        timing=timing_seconds,
    )


# Confidence tiers for bbox evidence, since neither InternVL's grounding output nor
# the Otsu fallback carries a calibrated confidence value. This module's own choice,
# not something specified in any project doc — same pattern as
# app.tools.fusion.reconcile's _SAR_ONLY_CONFIDENCE, flagged here for the same
# reason: an honest, disclosed tier beats a fabricated precise number, but it is
# still an authored guess. Native grounding is the model directly answering the
# grounding prompt (uncorroborated, like SAR alone); the Otsu fallback is a
# deterministic heuristic with no model judgment behind it at all, so it sits lower
# but still above RULE-VERIFY-02's confidence floor (0.30) so a real fallback bbox
# is not silently dropped.
_BBOX_NATIVE_CONFIDENCE = 0.75
_BBOX_OTSU_CONFIDENCE = 0.50


def build_bbox_evidence(
    *,
    asset: ImageInput,
    model_id: str,
    bbox: list[int],
    label: str,
    source: str,
    timing_seconds: float,
) -> Evidence:
    """Create traceable bbox evidence, honestly labeled by which path produced it."""
    if source not in ("internvl_native", "otsu_fallback"):
        raise ValueError(f"unknown bbox source: {source!r}")
    confidence = _BBOX_NATIVE_CONFIDENCE if source == "internvl_native" else _BBOX_OTSU_CONFIDENCE
    return Evidence(
        id=str(uuid.uuid4()),
        tool="internvl_vqa" if source == "internvl_native" else "otsu_fallback",
        type=EvidenceType.BBOX,
        payload={
            "source_asset_id": asset.id,
            "source_filename": asset.metadata.get("filename"),
            "bbox": list(bbox),
            "label": label,
            "source": source,
            "model_id": model_id if source == "internvl_native" else None,
        },
        confidence=confidence,
        timing=timing_seconds,
    )


def assemble_answer(
    *,
    text: str,
    evidence: list[Evidence],
    trace: ExecutionTrace,
    abstained: bool,
    abstention_reason: str | None,
) -> Answer:
    """Map verified text, canonical evidence, and trace into the existing response contract."""
    confidence = sum(item.confidence for item in evidence) / len(evidence) if evidence else 0.0
    return Answer(
        text=text,
        evidence=evidence,
        trace=trace,
        confidence=confidence,
        abstained=abstained,
        abstention_reason=abstention_reason,
    )
