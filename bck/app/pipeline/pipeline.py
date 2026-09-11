"""Compose real ingestion, routing, tool dispatch (VQA, change detection, fusion),
verification, evidence, and tracing stages.
"""

from __future__ import annotations

import os

import numpy as np
import rasterio

from app.contracts import Answer, Evidence, Modality, QueryRequest
from app.core.raster_artifacts import write_mask_artifact
from app.db import persist_trace
from app.evidence import assemble_answer, build_bbox_evidence, build_vqa_evidence
from app.ingestion import (
    IngestedRaster,
    InvalidRasterError,
    RasterUpload,
    UnsupportedRasterError,
    ingest_raster,
)
from app.models import InternVLAdapter, InternVLModelError
from app.pipeline.stages import PipelineError, PipelineUpload, TraceRecorder
from app.router import DispatchPlan, route
from app.tools.change_detection.detector import detect_change
from app.tools.fusion.cloud_detector import detect_clouds
from app.tools.fusion.despeckle import lee_filter
from app.tools.fusion.guards import InsufficientValidSupportError
from app.tools.fusion.reconcile import reconcile_sar_optical
from app.tools.fusion.sar_scale import SarScale
from app.tools.fusion.sar_water_mask import otsu_water_mask
from app.tools.vqa_grounding import VqaModel, VqaToolError, VqaToolResult, execute_vqa
from app.verification import VerificationPolicy, verification_trace_params, verify

_default_model: InternVLAdapter | None = None

# Matches the fixture path convention already used by tests/test_detector.py and
# tests/change_detection/test_change_summary.py. Overridable for real deployment,
# same pattern as app.models.internvl.ADAPTER_PATH.
_DEFAULT_BIT_CHECKPOINT_PATH = "checkpoints/BIT_LEVIR/best_ckpt.pt"
BIT_CHECKPOINT_PATH = os.environ.get("BIT_CHECKPOINT_PATH", _DEFAULT_BIT_CHECKPOINT_PATH)

# Matches the value used throughout tests/test_fusion_*.py. A real per-sensor
# noise-equivalent sigma-zero belongs in calibration metadata this pipeline has
# no access to from a plain GeoTIFF upload (same gap as the dB-scale assumption
# in _run_fusion_tool below — both flagged there, not invented silently here).
_SAR_NOISE_VARIANCE = 0.005

_SUPPORTED_TOOLS = frozenset({"vqa_grounding", "change_detection", "fusion"})


def _get_default_model() -> InternVLAdapter:
    global _default_model
    if _default_model is None:
        _default_model = InternVLAdapter()
    return _default_model


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
    if dispatch_plan.tool_name == "vqa_grounding":
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
    )
    if decision.degradation_notice is not None:
        recorder.record(
            "quality",
            "degradation_detected",
            params=decision.degradation_notice.model_dump(mode="json"),
        )

    verified_ids = {item.id for item in decision.verified_evidence}

    if dispatch_plan.tool_name == "vqa_grounding":
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
    )
    if decision.degradation_notice is not None:
        answer = answer.model_copy(update={"degradation_notice": decision.degradation_notice})
    try:
        persist_trace(trace, _json_safe_evidence(evidence_list))
    except Exception as error:
        _fail(recorder, stage="persistence", message=str(error), status_code=500)

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
) -> tuple[list[Evidence], tuple[str, ...], VqaToolResult]:
    """Single-image VQA/grounding: unchanged behavior from the original single-tool pipeline."""
    active_model = model or _get_default_model()
    source = _find_ingested(ingested, dispatch_plan.image_bindings["image"], role="image")
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
            question=dispatch_plan.task_parameters["prompt"],
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

    bbox_evidence: Evidence | None = None
    if tool_result.bbox is not None and tool_result.bbox_source is not None:
        bbox_evidence = build_bbox_evidence(
            asset=source.source,
            model_id=tool_result.model_id,
            bbox=tool_result.bbox,
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
    """Bi-temporal BIT change detection (ROHAN-002), mirroring the VQA dispatch shape."""
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
            "checkpoint_path": BIT_CHECKPOINT_PATH,
        },
    )
    try:
        # detector.py has no typed exception contract of its own (unlike VQA's
        # InternVLModelError/VqaToolError or fusion's InsufficientValidSupportError)
        # — a missing checkpoint file raises a bare FileNotFoundError from
        # torch.load, so this catches broadly rather than pretending a narrower
        # type exists. That gap belongs to detector.py, not silently papered
        # over here.
        evidence_list = detect_change(
            pre_image.source,
            post_image.source,
            BIT_CHECKPOINT_PATH,
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
    )
    return evidence_list


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
    )
    return evidence_list


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
