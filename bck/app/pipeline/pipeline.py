"""Compose real ingestion, routing, tool dispatch (VQA, change detection, fusion),
verification, evidence, and tracing stages.
"""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime, timedelta

import numpy as np
import rasterio
from PIL import Image
from skimage.measure import label, regionprops

from app.contracts import Answer, Evidence, EvidenceType, Modality, QueryRequest
from app.core.logging import get_logger
from app.core.raster_artifacts import write_mask_artifact
from app.db import persist_trace
from app.evidence import assemble_answer, build_bbox_evidence, build_vqa_evidence
from app.history import get_sync_session as get_history_session
from app.history import record_query
from app.inference import remote
from app.inference.identity import EXPECTED_MODEL_IDENTITY
from app.inference.remote import InferenceError
from app.ingestion import (
    EoGate,
    EoGateStatus,
    IngestedRaster,
    InvalidRasterError,
    RasterUpload,
    UnsupportedRasterError,
    evaluate_eo_gates,
    ingest_raster,
)
from app.pipeline.cached_demo import find_cached_answer
from app.pipeline.stages import PipelineError, PipelineUpload, TraceRecorder
from app.router import (
    MAX_TOOL_CALLS,
    PLANNED_TOOL_SEQUENCE,
    DispatchPlan,
    VetoReasonCode,
    route,
)
from app.tools.change_detection.bit_io import (
    decode_mask_png,
    decode_probability_png,
    to_bit_input,
)
from app.tools.change_detection.detector import build_change_evidence
from app.tools.fusion.cloud_detector import detect_clouds
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.guards import InsufficientValidSupportError
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask
from app.tools.vqa_grounding import (
    VqaModel,
    VqaPasses,
    VqaToolError,
    VqaToolResult,
    build_vqa_result,
    execute_vqa,
)
from app.tools.vqa_grounding.tool import to_vqa_input
from app.verification import VerificationPolicy, verification_trace_params, verify

# InternVL and BIT run in the inference Space (app.inference.remote); this process never
# imports torch. An injected `model` (tests) still runs VQA in-process.
logger = get_logger(__name__)

_INFERENCE_STATUS = {"INFERENCE_UNAVAILABLE": 503, "INFERENCE_QUOTA": 429}
_INFERENCE_SUGGESTED_ACTION = {
    "INFERENCE_UNAVAILABLE": (
        "The model service is unavailable or still waking up. Try again in a minute, "
        "or pick a demo preset."
    ),
    "INFERENCE_QUOTA": "The GPU quota for the model service is used up. Try again later.",
}

# Matches the value used throughout tests/test_fusion_*.py. A real per-sensor
# noise-equivalent sigma-zero belongs in calibration metadata this pipeline has
# no access to from a plain GeoTIFF upload (same gap as the dB-scale assumption
# in _run_fusion_tool below — both flagged there, not invented silently here).
_SAR_NOISE_VARIANCE = 0.005

_SUPPORTED_TOOLS = frozenset({"vqa_grounding", "change_detection", "fusion"})

# A FAIL from any EO gate vetoes through the same _fail path as a router veto, with
# one distinct reason code per gate.
_EO_GATE_VETOES: dict[EoGate, tuple[VetoReasonCode, str]] = {
    EoGate.CRS_CONSISTENCY: (
        VetoReasonCode.EO_CRS_MISMATCH,
        "Reproject the rasters to a common CRS before uploading.",
    ),
    EoGate.GEOGRAPHIC_OVERLAP: (
        VetoReasonCode.EO_INSUFFICIENT_OVERLAP,
        "Upload rasters that cover the same area of interest.",
    ),
    EoGate.GSD_MATCH: (
        VetoReasonCode.EO_GSD_MISMATCH,
        "Resample the rasters to a common ground sample distance before uploading.",
    ),
    EoGate.ACQUISITION_ORDER: (
        VetoReasonCode.EO_ACQUISITION_ORDER_REVERSED,
        "Swap the images: Slot 1 must hold the earlier acquisition, Slot 2 the later one.",
    ),
}


def _find_ingested(ingested: list[IngestedRaster], image_id: str, *, role: str) -> IngestedRaster:
    """Resolve one dispatch-plan image binding back to its ingested raster."""
    for item in ingested:
        if item.source.id == image_id:
            return item
    raise ValueError(f"dispatch plan bound '{role}' to unknown image id '{image_id}'")


def _narrative_text(evidence_list: list[Evidence]) -> str:
    """Join each surviving evidence item's own human-readable note/description.

    Unlike VQA text, change-detection and fusion evidence already carry a
    deterministic, tool-computed sentence describing what was found — there is
    no separate LLM claim to fact-check the way VQA's raw model answer is, so
    this just surfaces that sentence rather than re-deriving one.
    """
    parts = [
        item.payload.get("note") or item.payload.get("description") or "" for item in evidence_list
    ]
    return " ".join(part for part in parts if part).strip()


def _json_safe(value: object) -> object:
    """Recursively convert numpy arrays/scalars to plain JSON-safe Python values.

    Evidence payloads legitimately carry raster arrays (water_mask, valid_mask,
    change_mask, ...) — that is the fusion/change-detection tools' real
    contract, not something to strip from them. Pydantic's own
    `Evidence.model_dump(mode="json")`, used at the persistence boundary, has
    no numpy support and raises on these, so this converts right before that
    boundary instead of asking every tool to avoid returning arrays it
    genuinely computed.
    """
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value


def _json_safe_evidence(evidence_list: list[Evidence]) -> list[Evidence]:
    """Copy each evidence item with a JSON-safe payload, for persistence only.

    The in-memory `Answer` returned to callers keeps the original evidence
    (real ndarrays intact) — only what actually reaches persist_trace is
    converted.
    """
    return [item.model_copy(update={"payload": _json_safe(item.payload)}) for item in evidence_list]


def run(
    *,
    query: str,
    uploads: list[PipelineUpload],
    model: VqaModel | None = None,
    policy: VerificationPolicy | None = None,
    user_id: str | None = None,
    prefer_cached: bool = False,
) -> Answer:
    """Answer a query: a demo preset's recorded run, or a live run of the pipeline.

    `prefer_cached` (a demo preset without an explicit "run live") returns the preset's
    recorded answer immediately when the uploads and question match it exactly. A live run
    that fails only because inference is unavailable or over quota falls back to the same
    recording, marked with that reason; with no matching recording the error stands.
    """
    contents = [upload.content for upload in uploads]
    if prefer_cached and model is None:
        cached = find_cached_answer(query=query, upload_contents=contents, reason="demo_default")
        if cached is not None:
            return cached
    try:
        return _run_live(query=query, uploads=uploads, model=model, policy=policy, user_id=user_id)
    except PipelineError as error:
        if error.reason_code not in _INFERENCE_STATUS:
            raise
        cached = find_cached_answer(query=query, upload_contents=contents, reason=error.reason_code)
        if cached is None:
            raise
        logger.warning("Live inference failed (%s); serving the recorded demo run.", error)
        return cached


def _run_live(
    *,
    query: str,
    uploads: list[PipelineUpload],
    model: VqaModel | None,
    policy: VerificationPolicy | None,
    user_id: str | None,
) -> Answer:
    """Run the real vertical slice for whichever tool the router dispatches to."""
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
                "modality": upload.modality.value if upload.modality is not None else None,
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
    ingestion_started = datetime.now(UTC)
    try:
        ingested = [
            ingest_raster(
                RasterUpload(
                    id=upload.id,
                    filename=upload.filename,
                    content_type=upload.content_type,
                    content=upload.content,
                    modality=upload.modality,
                    capture_order=upload.capture_order,
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
        started_at=ingestion_started,
    )

    if len(ingested) >= 2:
        gate_results = evaluate_eo_gates([item.source for item in ingested])
        for result in gate_results:
            recorder.record(
                "validation",
                "eo_gates",
                params={
                    "gate": result.gate.value,
                    "status": result.status.value,
                    "reason": result.reason,
                    **result.details,
                },
                started_at=result.started_at,
                completed_at=result.completed_at,
            )
        failed = next(
            (result for result in gate_results if result.status == EoGateStatus.FAIL), None
        )
        if failed is not None:
            reason_code, suggested_action = _EO_GATE_VETOES[failed.gate]
            _fail(
                recorder,
                stage="validation",
                message=failed.reason,
                status_code=422,
                reason_code=reason_code.value,
                suggested_action=suggested_action,
            )

    # AC3: Compute cloud-cover fraction at most once per optical input and reuse downstream
    for item in ingested:
        source = item.source
        if source.modality == Modality.OPTICAL:
            cloud_fraction = source.metadata.get("cloud_fraction")
            if (
                cloud_fraction is None
                and source.metadata.get("band_count") in (10, 13)
                and source.path
            ):
                with rasterio.open(source.path) as dataset:
                    arr = dataset.read()
                reflectance = np.moveaxis(arr, 0, -1).astype(np.float32) / 10000.0
                cloud_res = detect_clouds(reflectance)
                source.metadata["cloud_fraction"] = float(cloud_res.mask.mean())

    request = QueryRequest(query=query.strip(), images=[item.source for item in ingested])

    recorder.record("router", "routing_started")
    routing_started = datetime.now(UTC)
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
            "tool_sequence": dispatch_plan.tool_sequence if dispatch_plan is not None else [],
            "planned_sequence": PLANNED_TOOL_SEQUENCE.get(decision.intent.task_type, []),
            "supported": decision.is_dispatched,
            "reason": route_reason,
        },
        started_at=routing_started,
    )
    if not decision.is_dispatched or dispatch_plan is None:
        _fail(
            recorder,
            stage="routing",
            message=route_reason,
            status_code=422,
            reason_code=decision.veto.reason_code.value if decision.veto is not None else None,
            suggested_action=decision.veto.suggested_action if decision.veto is not None else None,
        )
    if dispatch_plan.tool_name not in _SUPPORTED_TOOLS:
        _fail(
            recorder,
            stage="routing",
            message=(
                "The selected tool is unavailable in this vertical slice: "
                f"{dispatch_plan.tool_name}"
            ),
            status_code=422,
        )

    tool_result: VqaToolResult | None = None
    if dispatch_plan.followups:
        candidate_evidence_list, supporting_observations, tool_result = _run_change_then_describe(
            recorder, ingested, dispatch_plan, model
        )
    elif dispatch_plan.tool_name == "vqa_grounding":
        candidate_evidence_list, supporting_observations, tool_result = _run_vqa_tool(
            recorder, ingested, dispatch_plan, model
        )
    elif dispatch_plan.tool_name == "change_detection":
        candidate_evidence_list = _run_change_detection_tool(recorder, ingested, dispatch_plan)
        supporting_observations = ()
        source = _find_ingested(
            ingested, dispatch_plan.image_bindings["pre_image"], role="pre_image"
        )
        candidate_evidence_list = _enrich_mask_evidence(candidate_evidence_list, source.source)
    else:
        candidate_evidence_list = _run_fusion_tool(recorder, ingested, dispatch_plan)
        supporting_observations = ()
        source_id = dispatch_plan.image_bindings.get("optical_image")
        source = _find_ingested(ingested, source_id, role="optical_image")
        candidate_evidence_list = _enrich_mask_evidence(candidate_evidence_list, source.source)

    recorder.record("verification", "verification_started")
    verification_started = datetime.now(UTC)
    decision = verify(
        evidence=candidate_evidence_list,
        raw_query=request.query,
        images=[item.source for item in ingested],
        policy=policy,
        supporting_observations=supporting_observations,
    )
    recorder.record(
        "verification",
        "verification_completed",
        params=verification_trace_params(decision),
        confidence=decision.effective_confidence,
        evidence_ids=[item.id for item in decision.verified_evidence],
        started_at=verification_started,
    )
    if decision.degradation_notice is not None:
        recorder.record(
            "quality",
            "degradation_detected",
            params=decision.degradation_notice.model_dump(mode="json"),
        )

    evidence_started = datetime.now(UTC)
    verified_ids = {item.id for item in decision.verified_evidence}

    answer_confidence: float | None = None
    if dispatch_plan.followups:
        evidence_list, verified_text = _combine_change_and_vqa(
            candidate_evidence_list, decision.verified_evidence, tool_result
        )
        evidence_list = _json_safe_evidence(evidence_list)
        # Design choice, not a sourced rule: a two-step answer is only as reliable as its
        # weakest step, so its confidence is the minimum over the surviving evidence.
        answer_confidence = min((item.confidence for item in evidence_list), default=0.0)
    elif dispatch_plan.tool_name == "vqa_grounding":
        assert tool_result is not None
        candidate_evidence = candidate_evidence_list[0]
        bbox_evidence = candidate_evidence_list[1] if len(candidate_evidence_list) > 1 else None
        source = _find_ingested(ingested, dispatch_plan.image_bindings["image"], role="image")
        text_survived = candidate_evidence.id in verified_ids
        matched_text = next(
            (item for item in decision.verified_evidence if item.id == candidate_evidence.id),
            None,
        )
        salvaged_text = matched_text.payload.get("verified_answer") if matched_text else None
        verified_text = (salvaged_text or tool_result.raw_answer) if text_survived else ""
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
        if text_survived:
            evidence = evidence.model_copy(
                update={"id": candidate_evidence.id, "confidence": decision.effective_confidence}
            )
        evidence_list = [evidence] if text_survived else []
        if bbox_evidence is not None and bbox_evidence.id in verified_ids:
            evidence_list.append(bbox_evidence)
    else:
        evidence_list = [item for item in candidate_evidence_list if item.id in verified_ids]
        verified_text = _narrative_text(evidence_list)

        # Tool payloads may contain NumPy masks for in-process verification;
        # the HTTP response must contain only JSON-native values.
        evidence_list = _json_safe_evidence(evidence_list)

    recorder.record(
        "evidence",
        "evidence_created",
        params={
            "evidence_types": [item.type.value for item in evidence_list],
            "source_asset_ids": list(dispatch_plan.image_bindings.values()),
        },
        evidence_ids=[item.id for item in evidence_list],
        started_at=evidence_started,
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
    trace = recorder.build()
    answer = assemble_answer(
        text=verified_text,
        evidence=evidence_list,
        trace=trace,
        abstained=decision.is_abstained,
        abstention_reason=decision.abstention_reason,
        confidence=answer_confidence,
    )
    if decision.degradation_notice is not None:
        answer = answer.model_copy(update={"degradation_notice": decision.degradation_notice})
    try:
        persist_trace(trace, _json_safe_evidence(evidence_list))
    except Exception as error:
        _fail(recorder, stage="persistence", message=str(error), status_code=500)

    # History is a best-effort convenience feature, not part of the answer contract: unlike
    # persist_trace above (a deliberate P0 hard-failure), a broken history write must never
    # turn a successful answer into a 500 — swallow and log instead.
    try:
        modality_str = (
            "fusion" if dispatch_plan.tool_name == "fusion" else ingested[0].source.modality.value
        )
        with get_history_session() as history_session:
            record_query(
                history_session,
                user_id=user_id,
                query_text=request.query,
                answer_text=answer.text,
                confidence=answer.confidence,
                modality=modality_str,
            )
    except Exception:
        logger.exception("history write failed; answer is unaffected")

    return answer


def _enrich_mask_evidence(evidence_list: list[Evidence], source) -> list[Evidence]:
    """Attach shared TiTiler URLs to BIT and fusion mask evidence."""
    enriched: list[Evidence] = []
    for evidence in evidence_list:
        mask = next(
            (
                evidence.payload[key]
                for key in ("change_mask", "water_mask")
                if isinstance(evidence.payload.get(key), np.ndarray)
            ),
            None,
        )
        raster_url = write_mask_artifact(mask, source) if mask is not None else None
        if raster_url is not None:
            evidence = evidence.model_copy(
                update={"payload": {**evidence.payload, "raster_url": raster_url}}
            )
        enriched.append(evidence)
    return enriched


def _run_vqa_tool(
    recorder: TraceRecorder,
    ingested: list[IngestedRaster],
    dispatch_plan: DispatchPlan,
    model: VqaModel | None,
    region: tuple[int, int, int, int] | None = None,
) -> tuple[list[Evidence], tuple[str, ...], VqaToolResult]:
    """Single-image VQA/grounding in the inference Space (or an injected in-process model).

    With `region` (left, top, right, bottom in visual pixels) the model sees only that crop;
    its box is shifted back to full-frame pixels before georeferencing.
    """
    source = _find_ingested(ingested, dispatch_plan.image_bindings["image"], role="image")
    image = source.visual if region is None else source.visual.crop(region)
    question = dispatch_plan.task_parameters["prompt"]
    model_id = model.model_id if model is not None else EXPECTED_MODEL_IDENTITY["base_model"]
    device = model.device if model is not None else "inference_space"
    recorder.record(
        "tools.vqa_grounding",
        "vqa_started",
        params={"asset_id": source.source.id, "model_id": model_id},
    )
    recorder.record(
        "models.internvl",
        "internvl_inference_started",
        params={"model_id": model_id, "device": device},
    )
    inference_started = datetime.now(UTC)
    if model is None:
        tool_result = _run_remote_vqa(recorder, source, question, image)
    else:
        try:
            tool_result = execute_vqa(
                image=image,
                question=question,
                source_asset_id=source.source.id,
                model=model,
            )
        except VqaToolError as error:
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
        started_at=inference_started,
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

    bbox_evidence: Evidence | None = None
    if tool_result.bbox is not None and tool_result.bbox_source is not None:
        bbox = tool_result.bbox
        if region is not None:
            left, top = region[0], region[1]
            bbox = [bbox[0] + left, bbox[1] + top, bbox[2] + left, bbox[3] + top]
        bbox_evidence = build_bbox_evidence(
            asset=source.source,
            model_id=tool_result.model_id,
            bbox=bbox,
            visual_size=source.visual.size,
            label=tool_result.bbox_label or tool_result.raw_answer,
            source=tool_result.bbox_source,
            timing_seconds=tool_result.timing_seconds,
        )

    candidate_evidence_list = [candidate_evidence]
    if bbox_evidence is not None:
        candidate_evidence_list.append(bbox_evidence)

    return candidate_evidence_list, tool_result.supporting_observations, tool_result


def _run_change_detection_tool(
    recorder: TraceRecorder,
    ingested: list[IngestedRaster],
    dispatch_plan: DispatchPlan,
) -> list[Evidence]:
    """Bi-temporal BIT change detection (ROHAN-002): BIT in the inference Space, gating,
    confidence and summary here."""
    pre_image = _find_ingested(
        ingested, dispatch_plan.image_bindings["pre_image"], role="pre_image"
    )
    post_image = _find_ingested(
        ingested, dispatch_plan.image_bindings["post_image"], role="post_image"
    )
    recorder.record(
        "tools.change_detection",
        "change_detection_started",
        params={
            "pre_image_id": pre_image.source.id,
            "post_image_id": post_image.source.id,
            "inference": "inference_space",
        },
    )
    inference_started = datetime.now(UTC)
    started = time.perf_counter()
    try:
        pre_input = to_bit_input(Image.open(pre_image.source.path))
        post_input = to_bit_input(Image.open(post_image.source.path))
        call_started = datetime.now(UTC)
        result = remote.change_detect(pre_input, post_input)
    except InferenceError as error:
        _fail_inference(recorder, error)
    except Exception as error:
        # Unreadable inputs have no typed exception contract; keep the clean 503.
        _fail(
            recorder,
            stage="model_inference",
            message=f"Change detection could not complete: {error}",
            status_code=503,
        )
    call_completed = datetime.now(UTC)
    _record_remote_call(
        recorder,
        module="inference.remote",
        action="remote_change_detect_call",
        started_at=call_started,
        completed_at=call_completed,
        space_total_seconds=result.total_seconds,
        model_identity=result.model_identity,
        passes=[("models.change_detection.bit", "bit_forward_pass", result.inference_seconds)],
    )
    try:
        evidence_list = build_change_evidence(
            probability_changed=decode_probability_png(result.probability_png),
            predicted_mask=decode_mask_png(result.mask_png),
            image_a=pre_image.source,
            image_b=post_image.source,
            started=started,
        )
    except Exception as error:
        _fail(
            recorder,
            stage="model_inference",
            message=f"Change detection could not complete: {error}",
            status_code=503,
        )
    recorder.record(
        "models.change_detection.bit",
        "bit_inference_completed",
        params={
            "confounder_suppressed": evidence_list[0].payload.get("confounder_suppressed"),
            "changed_percentage": evidence_list[0].payload.get("changed_percentage"),
            "timing_seconds": evidence_list[0].timing,
        },
        started_at=inference_started,
    )
    return evidence_list


# Minimum crop side (post-image pixels) sent to VQA from the change -> describe handoff, so
# a tiny changed blob still arrives with surrounding context.
_MIN_CHANGE_CONTEXT_PX = 128
_CHANGE_DESCRIBE_SEQUENCE = ["change_detection", "vqa_grounding"]


def _run_change_then_describe(
    recorder: TraceRecorder,
    ingested: list[IngestedRaster],
    dispatch_plan: DispatchPlan,
    model: VqaModel | None,
) -> tuple[list[Evidence], tuple[str, ...], VqaToolResult | None]:
    """The one fixed two-tool sequence: BIT change detection, then VQA on the post image
    cropped to the largest changed region. Not a general planner.

    Step 2 depends on step 1's output (the crop), so they run strictly in order. With no
    changed region left after the confounder gate, step 2 is skipped and recorded as such.
    """
    if dispatch_plan.tool_sequence != _CHANGE_DESCRIBE_SEQUENCE:
        _fail(
            recorder,
            stage="routing",
            message=f"Unsupported tool sequence: {dispatch_plan.tool_sequence}",
            status_code=422,
        )
    total = len(dispatch_plan.tool_sequence)
    tool_calls = 0

    def _count_tool_call() -> None:
        nonlocal tool_calls
        tool_calls += 1
        if tool_calls > MAX_TOOL_CALLS:
            _fail(
                recorder,
                stage="pipeline",
                message=f"Tool-call cap reached (MAX_TOOL_CALLS={MAX_TOOL_CALLS}).",
                status_code=500,
            )

    # Step 1: change detection
    step_started = datetime.now(UTC)
    recorder.record(
        "pipeline",
        "sequence_step_started",
        params={"index": 1, "of": total, "tool": "change_detection"},
    )
    _count_tool_call()
    change_evidence = _run_change_detection_tool(recorder, ingested, dispatch_plan)
    post_image = _find_ingested(
        ingested, dispatch_plan.image_bindings["post_image"], role="post_image"
    )
    pre_image = _find_ingested(
        ingested, dispatch_plan.image_bindings["pre_image"], role="pre_image"
    )
    change_evidence = _enrich_mask_evidence(change_evidence, pre_image.source)
    recorder.record(
        "pipeline",
        "sequence_step_completed",
        params={"index": 1, "of": total, "tool": "change_detection"},
        evidence_ids=[item.id for item in change_evidence],
        started_at=step_started,
    )

    # Handoff: largest connected changed component -> padded crop of the post image
    step = dispatch_plan.followups[0]
    mask = np.asarray(change_evidence[0].payload["change_mask"], dtype=bool)
    component = _largest_change_component(mask)
    if component is None:
        recorder.record(
            "pipeline",
            "sequence_short_circuit",
            params={
                "skipped_tool": step.tool_name,
                "reason": "no changed region left after the confounder gate",
            },
        )
        return change_evidence, (), None
    area_px, component_bbox = component
    region = _padded_region(
        component_bbox, mask_shape=mask.shape, image_size=post_image.visual.size
    )
    recorder.record(
        "pipeline",
        "sequence_handoff",
        params={
            "from_tool": "change_detection",
            "to_tool": step.tool_name,
            "input": step.input_from_previous,
            "component_area_px": area_px,
            "component_bbox_mask_px": list(component_bbox),
            "mask_size": [mask.shape[1], mask.shape[0]],
            "connectivity": 8,
            "crop_box_px": list(region),
            "crop_size": [region[2] - region[0], region[3] - region[1]],
            "min_context_px": _MIN_CHANGE_CONTEXT_PX,
        },
    )

    # Step 2: VQA on the crop
    step_started = datetime.now(UTC)
    recorder.record(
        "pipeline",
        "sequence_step_started",
        params={"index": 2, "of": total, "tool": step.tool_name},
    )
    _count_tool_call()
    vqa_plan = DispatchPlan(
        tool_name=step.tool_name,
        image_bindings=step.image_bindings,
        task_parameters=step.task_parameters,
    )
    vqa_evidence, observations, tool_result = _run_vqa_tool(
        recorder, ingested, vqa_plan, model, region=region
    )
    recorder.record(
        "pipeline",
        "sequence_step_completed",
        params={"index": 2, "of": total, "tool": step.tool_name},
        evidence_ids=[item.id for item in vqa_evidence],
        started_at=step_started,
    )
    return change_evidence + vqa_evidence, observations, tool_result


def _largest_change_component(mask: np.ndarray) -> tuple[int, tuple[int, int, int, int]] | None:
    """(pixel area, (left, top, right, bottom)) of the largest 8-connected changed region."""
    labeled = label(mask, connectivity=2)
    if labeled.max() == 0:
        return None
    largest = max(regionprops(labeled), key=lambda region: region.area)
    min_row, min_col, max_row, max_col = largest.bbox
    return int(largest.area), (int(min_col), int(min_row), int(max_col), int(max_row))


def _padded_region(
    component_bbox: tuple[int, int, int, int],
    *,
    mask_shape: tuple[int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    """Scale a mask-space box to image pixels, then grow it to at least
    _MIN_CHANGE_CONTEXT_PX per side (centred), clamped to the image bounds."""
    width, height = image_size
    scale_x = width / mask_shape[1]
    scale_y = height / mask_shape[0]
    left, top, right, bottom = component_bbox

    def _span(low: float, high: float, size: int) -> tuple[int, int]:
        low_px, high_px = math.floor(low), math.ceil(high)
        target = min(max(high_px - low_px, _MIN_CHANGE_CONTEXT_PX), size)
        start = low_px - (target - (high_px - low_px)) // 2
        start = max(0, min(start, size - target))
        return start, start + target

    x0, x1 = _span(left * scale_x, right * scale_x, width)
    y0, y1 = _span(top * scale_y, bottom * scale_y, height)
    return x0, y0, x1, y1


def _combine_change_and_vqa(
    candidates: list[Evidence],
    verified: list[Evidence],
    tool_result: VqaToolResult | None,
) -> tuple[list[Evidence], str]:
    """Surviving evidence of both steps (verified versions) and one answer text."""
    verified_by_id = {item.id: item for item in verified}
    kept = [verified_by_id[item.id] for item in candidates if item.id in verified_by_id]
    change_text = _narrative_text([item for item in kept if item.tool == "change_detection.bit"])
    vqa_text = ""
    vqa_item = next(
        (item for item in kept if item.tool == "internvl_vqa" and item.type == EvidenceType.TEXT),
        None,
    )
    if vqa_item is not None and tool_result is not None:
        answer = vqa_item.payload.get("verified_answer") or tool_result.raw_answer
        vqa_text = f"In the largest changed region: {answer}"
    return kept, " ".join(part for part in (change_text, vqa_text) if part)


def _run_remote_vqa(
    recorder: TraceRecorder, source: IngestedRaster, question: str, image: Image.Image
) -> VqaToolResult:
    """Send `image` at model input size to the Space; parse and map results back here."""
    started = time.perf_counter()
    call_started = datetime.now(UTC)
    try:
        result = remote.vqa_ground(to_vqa_input(image), question)
    except InferenceError as error:
        _fail_inference(recorder, error)
    _record_remote_call(
        recorder,
        module="inference.remote",
        action="remote_vqa_call",
        started_at=call_started,
        completed_at=datetime.now(UTC),
        space_total_seconds=result.total_seconds,
        model_identity=result.model_identity,
        passes=[
            ("models.internvl", "internvl_answer_pass", result.answer_seconds),
            ("models.internvl", "internvl_grounding_pass", result.grounding_seconds),
            ("models.internvl", "internvl_bbox_pass", result.bbox_seconds),
        ],
    )
    identity = result.model_identity
    passes = VqaPasses(
        raw_answer=result.raw_answer,
        raw_grounding_output=result.raw_grounding_output,
        raw_bbox_output=result.raw_bbox_output,
        answer_seconds=result.answer_seconds,
        grounding_seconds=result.grounding_seconds,
        bbox_seconds=result.bbox_seconds,
    )
    # Boxes are re-parsed from InternVL's normalized <box> text against the image that was
    # sent (full visual or crop) at its original resolution, so they map back exactly.
    return build_vqa_result(
        passes=passes,
        image=image,
        source_asset_id=source.source.id,
        model_id=f"{identity.get('base_model')} + {identity.get('adapter_name')}",
        device=str(identity.get("device", "inference_space")),
        started=started,
    )


def _record_remote_call(
    recorder: TraceRecorder,
    *,
    module: str,
    action: str,
    started_at: datetime,
    completed_at: datetime,
    space_total_seconds: float,
    model_identity: dict,
    passes: list[tuple[str, str, float | None]],
) -> None:
    """One step for the whole round trip, then one per model pass.

    Pass durations are measured on the Space. It doesn't report absolute times, so the pass
    steps are laid back to back ending when the response arrived; their durations are exact,
    their placement inside the round trip is not.
    """
    round_trip_seconds = (completed_at - started_at).total_seconds()
    recorder.record(
        module,
        action,
        params={
            "round_trip_s": round_trip_seconds,
            "space_total_s": space_total_seconds,
            "network_and_queue_s": round_trip_seconds - space_total_seconds,
            "model_identity": model_identity,
        },
        started_at=started_at,
        completed_at=completed_at,
    )
    spans: list[tuple[str, str, float, datetime, datetime]] = []
    end = completed_at
    for pass_module, pass_action, seconds in reversed(passes):
        if seconds is None:
            continue
        start = end - timedelta(seconds=seconds)
        spans.append((pass_module, pass_action, seconds, start, end))
        end = start
    for pass_module, pass_action, seconds, start, end in reversed(spans):
        recorder.record(
            pass_module,
            pass_action,
            params={
                "duration_s": seconds,
                "measured_on": "inference_space",
                "timestamps": "anchored_to_response_arrival",
            },
            started_at=start,
            completed_at=end,
        )


def _fail_inference(recorder: TraceRecorder, error: InferenceError) -> None:
    _fail(
        recorder,
        stage="model_inference",
        message=str(error),
        status_code=_INFERENCE_STATUS[error.reason_code],
        reason_code=error.reason_code,
        suggested_action=_INFERENCE_SUGGESTED_ACTION[error.reason_code],
    )


def _run_fusion_tool(
    recorder: TraceRecorder,
    ingested: list[IngestedRaster],
    dispatch_plan: DispatchPlan,
) -> list[Evidence]:
    """Cross-modal SAR+optical fusion (ROHAN-003/B1): despeckle -> water mask -> reconcile."""
    optical_image = _find_ingested(
        ingested, dispatch_plan.image_bindings["optical_image"], role="optical_image"
    )
    sar_image = _find_ingested(
        ingested, dispatch_plan.image_bindings["sar_image"], role="sar_image"
    )
    recorder.record(
        "tools.fusion",
        "fusion_started",
        params={"optical_image_id": optical_image.source.id, "sar_image_id": sar_image.source.id},
    )
    inference_started = datetime.now(UTC)

    band_count = optical_image.source.metadata.get("band_count")
    if band_count not in (10, 13):
        _fail(
            recorder,
            stage="model_inference",
            message=(
                "Fusion requires a 10- or 13-band optical scene for cloud detection; "
                f"got {band_count} bands"
            ),
            status_code=422,
        )

    with rasterio.open(sar_image.source.path) as sar_dataset:
        # The SAR VV band is assumed already sigma-nought dB-scale here, matching
        # the demo/canonical Sen1Floods11-derived assets this pipeline targets
        # (their own README declares "Unit: dB" — see tests/test_fusion_*.py's
        # identical assumption). A raw-DN SAR upload would need calibration.py's
        # per-scene K_cal/incidence-angle metadata first, which a plain GeoTIFF
        # upload does not carry — not handled here, flagged rather than guessed.
        sigma0_db = sar_dataset.read(1).astype(np.float64)
    valid_mask = np.isfinite(sigma0_db)

    with rasterio.open(optical_image.source.path) as optical_dataset:
        optical_array = optical_dataset.read()
    reflectance = np.moveaxis(optical_array, 0, -1).astype(np.float32) / 10000.0

    try:
        despeckled = lee_filter(
            sigma0_db, SarScale.DB, noise_variance=_SAR_NOISE_VARIANCE, valid_mask=valid_mask
        )
        water_mask = otsu_water_mask(despeckled, SarScale.DB, valid_mask=valid_mask)
        cloud_result = detect_clouds(reflectance)
        evidence_list = reconcile_sar_optical(
            despeckled, water_mask, cloud_result, valid_mask=valid_mask
        )
    except InsufficientValidSupportError as error:
        _fail(
            recorder,
            stage="model_inference",
            message=(
                "Fusion cannot proceed: the SAR scene's valid-data footprint is too "
                f"small to reconcile with optical evidence ({error})"
            ),
            status_code=422,
        )
    except ValueError as error:
        _fail(
            recorder,
            stage="model_inference",
            message=f"Fusion could not complete: {error}",
            status_code=422,
        )
    recorder.record(
        "models.fusion.despeckle_otsu",
        "fusion_inference_completed",
        params={
            "valid_pixel_count": evidence_list[0].payload.get("valid_pixel_count"),
            "support_fraction": evidence_list[0].payload.get("support_fraction"),
            "region_count": len(evidence_list),
        },
        started_at=inference_started,
    )
    return evidence_list


def _fail(
    recorder: TraceRecorder,
    *,
    stage: str,
    message: str,
    status_code: int,
    reason_code: str | None = None,
    suggested_action: str | None = None,
) -> None:
    """Record a safe failure event and stop the pipeline with its partial trace."""
    recorder.record(stage, "execution_failed", params={"message": message})
    raise PipelineError(
        message=message,
        stage=stage,
        status_code=status_code,
        trace=recorder.build(),
        reason_code=reason_code,
        suggested_action=suggested_action,
    )
