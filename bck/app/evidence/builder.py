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
