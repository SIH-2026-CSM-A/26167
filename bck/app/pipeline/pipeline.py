"""Compose real ingestion, routing, VQA, verification, evidence, and tracing stages."""

from __future__ import annotations

import os
from collections.abc import Callable

import numpy as np
import rasterio

from app.contracts import Answer, DegradationNotice, Evidence, ImageInput, Modality, QueryRequest
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
from app.tools.change_detection import execute_change_detection
from app.tools.fusion import execute_fusion
from app.tools.fusion.cloud_detector import CloudDetectionResult, detect_clouds
from app.tools.vqa_grounding import VqaModel, VqaToolError, execute_vqa
from app.verification import verification_trace_params, verify

_DEFAULT_CLOUD_DEGRADATION_THRESHOLD = 0.20

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
    change_detector: Callable[[ImageInput, ImageInput], list[Evidence]] | None = None,
    fusion_tool: Callable[[ImageInput, ImageInput], list[Evidence]] | None = None,
    bit_checkpoint_path: str | None = None,
) -> Answer:
    """Run the complete real multi-image and multi-modal pipeline and return canonical answer."""
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

    raw_threshold = os.getenv("SATQUERY_CLOUD_DEGRADATION_THRESHOLD")
    try:
        threshold = (
            float(raw_threshold)
            if raw_threshold is not None
            else _DEFAULT_CLOUD_DEGRADATION_THRESHOLD
        )
    except ValueError:
        threshold = _DEFAULT_CLOUD_DEGRADATION_THRESHOLD

    degraded_inputs: list[tuple[str, float]] = []
    cloud_results: dict[str, CloudDetectionResult] = {}

    for item in ingested:
        source = item.source
        if source.modality != Modality.OPTICAL:
            continue

        cloud_fraction = source.metadata.get("cloud_fraction")
        if cloud_fraction is None and source.metadata.get("band_count") in (10, 13) and source.path:
            with rasterio.open(source.path) as dataset:
                arr = dataset.read()
            reflectance = np.moveaxis(arr, 0, -1).astype(np.float32) / 10000.0
            cloud_result = detect_clouds(reflectance)
            cloud_results[source.id] = cloud_result
            cloud_fraction = cloud_result.cloud_fraction
            source.metadata["cloud_fraction"] = cloud_fraction

        if cloud_fraction is not None and cloud_fraction >= threshold:
            degraded_inputs.append((source.id, float(cloud_fraction)))

    degradation_notice: DegradationNotice | None = None
    if degraded_inputs:
        max_fraction = max(fraction for _, fraction in degraded_inputs)
        affected_ids = [img_id for img_id, _ in degraded_inputs]
        degradation_notice = DegradationNotice(
            degraded=True,
            metric_name="cloud_cover_fraction",
            metric_value=round(max_fraction, 4),
            threshold=round(threshold, 4),
            severity="warning",
            message=(
                f"Optical input '{affected_ids[0]}' exhibits {max_fraction * 100:.1f}% "
                f"cloud cover, exceeding the quality threshold of {threshold * 100:.1f}%."
            ),
            suggested_action=(
                "SAR-only fallback workflow recommended due to heavy cloud cover "
                "obscuring optical imagery."
            ),
            fallback_modality=Modality.SAR,
            affected_image_ids=affected_ids,
        )
        recorder.record(
            "quality",
            "degradation_detected",
            params=degradation_notice.model_dump(mode="json"),
        )

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
    if dispatch_plan.tool_name not in ("vqa_grounding", "change_detection", "fusion"):
        _fail(
            recorder,
            stage="routing",
            message=(
                "The selected tool is unavailable in this vertical slice: "
                f"{dispatch_plan.tool_name}"
            ),
            status_code=422,
        )

    if dispatch_plan.tool_name == "vqa_grounding":
        active_model = model or _get_default_model()
        bound_id = dispatch_plan.image_bindings.get("image")
        source = (
            next((item for item in ingested if item.source.id == bound_id), None)
            or ingested[0]
        )
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

        candidate_evidence = [
            build_vqa_evidence(
                asset=source.source,
                model_id=tool_result.model_id,
                raw_answer=tool_result.raw_answer,
                verified_answer=tool_result.raw_answer,
                supporting_observations=tool_result.supporting_observations,
                rejected_claims=(),
                timing_seconds=tool_result.timing_seconds,
            )
        ]
        supporting_observations = tool_result.supporting_observations

    elif dispatch_plan.tool_name == "change_detection":
        pre_id = dispatch_plan.image_bindings.get("pre_image")
        post_id = dispatch_plan.image_bindings.get("post_image")
        source_pre = next((item for item in ingested if item.source.id == pre_id), ingested[0])
        source_post = (
            next((item for item in ingested if item.source.id == post_id), None)
            or (ingested[1] if len(ingested) > 1 else ingested[0])
        )

        recorder.record(
            "tools.change_detection",
            "change_detection_started",
            params={"pre_image_id": source_pre.source.id, "post_image_id": source_post.source.id},
        )
        try:
            if change_detector is not None:
                candidate_evidence = change_detector(source_pre.source, source_post.source)
            else:
                candidate_evidence = execute_change_detection(
                    source_pre.source,
                    source_post.source,
                    checkpoint_path=bit_checkpoint_path,
                )
        except Exception as error:
            _fail(
                recorder,
                stage="model_inference",
                message=f"Change detection could not complete: {error}",
                status_code=503,
            )
        recorder.record(
            "tools.change_detection",
            "change_detection_completed",
            params={"evidence_count": len(candidate_evidence)},
        )
        supporting_observations = ()

    elif dispatch_plan.tool_name == "fusion":
        opt_id = dispatch_plan.image_bindings.get("optical_image")
        sar_id = dispatch_plan.image_bindings.get("sar_image")
        source_optical = next((item for item in ingested if item.source.id == opt_id), ingested[0])
        source_sar = (
            next((item for item in ingested if item.source.id == sar_id), None)
            or (ingested[1] if len(ingested) > 1 else ingested[0])
        )

        recorder.record(
            "tools.fusion",
            "fusion_started",
            params={
                "optical_image_id": source_optical.source.id,
                "sar_image_id": source_sar.source.id,
            },
        )
        try:
            if fusion_tool is not None:
                candidate_evidence = fusion_tool(source_optical.source, source_sar.source)
            else:
                candidate_evidence = execute_fusion(
                    source_optical.source,
                    source_sar.source,
                    cloud_result=cloud_results.get(source_optical.source.id),
                )
        except Exception as error:
            _fail(
                recorder,
                stage="model_inference",
                message=f"Cross-modal fusion could not complete: {error}",
                status_code=503,
            )
        recorder.record(
            "tools.fusion",
            "fusion_completed",
            params={
                "evidence_count": len(candidate_evidence),
                "regions": [e.payload.get("region") for e in candidate_evidence],
            },
        )
        supporting_observations = ()

    recorder.record("verification", "verification_started")
    decision = verify(
        evidence=candidate_evidence,
        raw_query=request.query,
        images=[item.source for item in ingested],
        supporting_observations=supporting_observations,
    )
    recorder.record(
        "verification",
        "verification_completed",
        params=verification_trace_params(decision),
        confidence=decision.effective_confidence,
        evidence_ids=[item.id for item in decision.verified_evidence],
    )

    if decision.is_abstained:
        verified_text = ""
        evidence_list = []
    elif dispatch_plan.tool_name == "vqa_grounding":
        salvaged_text = (
            decision.verified_evidence[0].payload.get("verified_answer")
            if decision.verified_evidence
            else None
        )
        verified_text = salvaged_text or tool_result.raw_answer
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
        evidence = evidence.model_copy(update={"confidence": decision.effective_confidence})
        evidence_list = [evidence]
    elif dispatch_plan.tool_name == "change_detection":
        verified_text = (
            decision.verified_evidence[0].payload.get(
                "description", "Change detection analysis completed."
            )
            if decision.verified_evidence
            else "No change detected."
        )
        evidence_list = decision.verified_evidence
    elif dispatch_plan.tool_name == "fusion":
        notes = [e.payload["note"] for e in decision.verified_evidence if "note" in e.payload]
        verified_text = " ".join(notes) if notes else "Cross-modal fusion analysis completed."
        evidence_list = decision.verified_evidence
    else:
        verified_text = ""
        evidence_list = decision.verified_evidence

    if dispatch_plan.tool_name == "vqa_grounding":
        recorder.record(
            "evidence",
            "evidence_created",
            params={"evidence_type": evidence.type.value, "source_asset_id": source.source.id},
            evidence_ids=[evidence.id] if not decision.is_abstained else [],
        )
    else:
        for ev in evidence_list:
            source_id = (
                ev.payload.get("source_asset_id")
                or ev.payload.get("source_image_a_id")
                or ev.payload.get("source_optical_id")
                or ""
            )
            recorder.record(
                "evidence",
                "evidence_created",
                params={"evidence_type": ev.type.value, "source_asset_id": source_id},
                evidence_ids=[ev.id],
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
        degradation_notice=degradation_notice,
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
