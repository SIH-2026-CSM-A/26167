"""Compose real ingestion, routing, VQA, verification, evidence, and tracing stages."""

from __future__ import annotations

from app.contracts import Answer, QueryRequest
from app.evidence import assemble_answer, build_vqa_evidence
from app.ingestion import (
    InvalidRasterError,
    RasterUpload,
    UnsupportedRasterError,
    ingest_raster,
)
from app.models import InternVL2Adapter, InternVLModelError
from app.pipeline.stages import PipelineError, PipelineUpload, TraceRecorder
from app.router import route_request
from app.tools.vqa_grounding import VqaModel, VqaToolError, execute_vqa
from app.verification import verify_answer

_default_model: InternVL2Adapter | None = None


def _get_default_model() -> InternVL2Adapter:
    global _default_model
    if _default_model is None:
        _default_model = InternVL2Adapter()
    return _default_model


def run(
    *,
    query: str,
    uploads: list[PipelineUpload],
    model: VqaModel | None = None,
) -> Answer:
    """Run the complete real single-image VQA slice and return the canonical answer."""
    recorder = TraceRecorder()
    recorder.record(
        "pipeline",
        "request_received",
        params={"query": query, "image_count": len(uploads)},
    )
    for upload in uploads:
        recorder.record(
            "api",
            "asset_received",
            params={
                "asset_id": upload.id,
                "filename": upload.filename,
                "content_type": upload.content_type,
                "size_bytes": len(upload.content),
                "modality": upload.modality.value,
            },
        )

    if not query.strip():
        _fail(
            recorder,
            stage="request_validation",
            message="A non-empty query is required.",
            status_code=422,
        )
    if not uploads:
        _fail(
            recorder,
            stage="request_validation",
            message="At least one image is required.",
            status_code=422,
        )

    recorder.record("ingestion", "asset_ingestion_started")
    try:
        ingested = [
            ingest_raster(
                RasterUpload(
                    id=upload.id,
                    filename=upload.filename,
                    content_type=upload.content_type,
                    content=upload.content,
                    modality=upload.modality,
                )
            )
            for upload in uploads
        ]
    except UnsupportedRasterError as error:
        _fail(recorder, stage="ingestion", message=str(error), status_code=415)
    except InvalidRasterError as error:
        _fail(recorder, stage="ingestion", message=str(error), status_code=422)

    recorder.record(
        "ingestion",
        "asset_ingested",
        params={
            "asset_ids": [item.source.id for item in ingested],
            "source_metadata": [item.source.metadata for item in ingested],
        },
    )
    request = QueryRequest(query=query.strip(), images=[item.source for item in ingested])

    recorder.record("router", "routing_started")
    decision = route_request(request)
    recorder.record(
        "router",
        "route_selected",
        params={
            "intent": decision.intent.value,
            "tool": decision.tool_name,
            "supported": decision.supported,
            "reason": decision.reason,
        },
    )
    if not decision.supported or decision.tool_name != "internvl_vqa":
        _fail(recorder, stage="routing", message=decision.reason, status_code=422)

    active_model = model or _get_default_model()
    source = ingested[0]
    recorder.record(
        "tools.vqa_grounding",
        "vqa_started",
        params={"asset_id": source.source.id, "model_id": active_model.model_id},
    )
    recorder.record(
        "models.internvl",
        "internvl_inference_started",
        params={"model_id": active_model.model_id, "device": active_model.device},
    )
    try:
        tool_result = execute_vqa(
            image=source.visual,
            question=request.query,
            source_asset_id=source.source.id,
            model=active_model,
        )
    except (InternVLModelError, VqaToolError) as error:
        _fail(
            recorder,
            stage="model_inference",
            message=f"InternVL VQA could not complete: {error}",
            status_code=503,
        )
    recorder.record(
        "models.internvl",
        "internvl_inference_completed",
        params={
            "model_id": tool_result.model_id,
            "device": tool_result.device,
            "timing_seconds": tool_result.timing_seconds,
            "raw_answer": tool_result.raw_answer,
            "supporting_observations": list(tool_result.supporting_observations),
        },
    )

    recorder.record("verification", "verification_started")
    verification = verify_answer(
        candidate_answer=tool_result.raw_answer,
        supporting_observations=tool_result.supporting_observations,
    )
    recorder.record(
        "verification",
        "verification_completed",
        params={
            "status": verification.status.value,
            "supported_claim_count": len(verification.supported_claims),
            "rejected_claim_count": len(verification.rejected_claims),
            "rejected_claims": list(verification.rejected_claims),
            "abstained": verification.abstained,
        },
    )

    evidence = build_vqa_evidence(
        asset=source.source,
        model_id=tool_result.model_id,
        raw_answer=tool_result.raw_answer,
        verified_answer=verification.verified_text,
        supporting_observations=tool_result.supporting_observations,
        rejected_claims=verification.rejected_claims,
        timing_seconds=tool_result.timing_seconds,
    )
    recorder.record(
        "evidence",
        "evidence_created",
        params={"evidence_type": evidence.type.value, "source_asset_id": source.source.id},
        evidence_ids=[evidence.id],
    )
    recorder.record(
        "pipeline",
        "response_completed",
        params={"abstained": verification.abstained, "evidence_count": 1},
        evidence_ids=[evidence.id],
    )
    return assemble_answer(
        text=verification.verified_text,
        evidence=[evidence],
        trace=recorder.build(),
        abstained=verification.abstained,
        abstention_reason=verification.abstention_reason,
    )


def _fail(
    recorder: TraceRecorder,
    *,
    stage: str,
    message: str,
    status_code: int,
) -> None:
    """Record a safe failure event and stop the pipeline with its partial trace."""
    recorder.record(stage, "execution_failed", params={"message": message})
    raise PipelineError(
        message=message,
        stage=stage,
        status_code=status_code,
        trace=recorder.build(),
    )
