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
from app.router import route
from app.tools.vqa_grounding import VqaModel, VqaToolError, execute_vqa
from app.verification import verification_trace_params, verify

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
    decision = route(request)
    dispatch_plan = decision.dispatch_plan
    route_reason = (
        decision.veto.message
        if decision.veto is not None
        else "Request satisfies router feasibility checks."
    )
    recorder.record(
        "router",
        "route_selected",
        params={
            "intent": decision.intent.task_type.value,
            "tool": dispatch_plan.tool_name if dispatch_plan is not None else None,
            "supported": decision.is_dispatched,
            "reason": route_reason,
        },
    )
    if not decision.is_dispatched or dispatch_plan is None:
        _fail(recorder, stage="routing", message=route_reason, status_code=422)
    if dispatch_plan.tool_name != "vqa_grounding":
        _fail(
            recorder,
            stage="routing",
            message=(
                "The selected tool is unavailable in this vertical slice: "
                f"{dispatch_plan.tool_name}"
            ),
            status_code=422,
        )

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

    candidate_evidence = build_vqa_evidence(
        asset=source.source,
        model_id=tool_result.model_id,
        raw_answer=tool_result.raw_answer,
        verified_answer=tool_result.raw_answer,
        supporting_observations=tool_result.supporting_observations,
        rejected_claims=(),
        timing_seconds=tool_result.timing_seconds,
    )

    recorder.record("verification", "verification_started")
    decision = verify(
        evidence=[candidate_evidence],
        raw_query=request.query,
        images=[item.source for item in ingested],
        supporting_observations=tool_result.supporting_observations,
    )
    recorder.record(
        "verification",
        "verification_completed",
        params=verification_trace_params(decision),
        confidence=decision.effective_confidence,
        evidence_ids=[item.id for item in decision.verified_evidence],
    )

    salvaged_text = (
        decision.verified_evidence[0].payload.get("verified_answer")
        if decision.verified_evidence
        else None
    )
    verified_text = "" if decision.is_abstained else (salvaged_text or tool_result.raw_answer)
    rejected_claims = tuple(d.description for d in decision.disagreements)
    evidence = build_vqa_evidence(
        asset=source.source,
        model_id=tool_result.model_id,
        raw_answer=tool_result.raw_answer,
        verified_answer=verified_text,
        supporting_observations=tool_result.supporting_observations,
        rejected_claims=rejected_claims,
        timing_seconds=tool_result.timing_seconds,
    )
    if not decision.is_abstained:
        evidence = evidence.model_copy(update={"confidence": decision.effective_confidence})

    evidence_list = [evidence] if not decision.is_abstained else []
    recorder.record(
        "evidence",
        "evidence_created",
        params={"evidence_type": evidence.type.value, "source_asset_id": source.source.id},
        evidence_ids=[evidence.id] if not decision.is_abstained else [],
    )
    recorder.record(
        "pipeline",
        "response_completed",
        params={
            "abstained": decision.is_abstained,
            "evidence_count": len(evidence_list),
        },
        evidence_ids=[item.id for item in evidence_list],
    )
    return assemble_answer(
        text=verified_text,
        evidence=evidence_list,
        trace=recorder.build(),
        abstained=decision.is_abstained,
        abstention_reason=decision.abstention_reason,
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
