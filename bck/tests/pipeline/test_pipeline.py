"""Full pipeline behavior tests using only the expensive-model boundary as a double."""

from app.contracts import Modality
from app.pipeline import PipelineUpload, run
from tests.helpers import DeterministicVqaModel, make_geotiff_bytes


def test_pipeline_verifies_model_output_and_builds_evidence_and_trace() -> None:
    """Canonical verification evaluates tool output and builds auditable trace."""
    model = DeterministicVqaModel(
        answer="A river is visible and industrial pollution is contaminating the water.",
        grounding="A river is visible in the scene.",
    )
    upload = PipelineUpload(
        id="asset-1",
        filename="scene.tif",
        content_type="image/tiff",
        content=make_geotiff_bytes(),
        modality=Modality.OPTICAL,
    )

    answer = run(
        query="What geographic feature is visible?",
        uploads=[upload],
        model=model,
    )

    assert answer.abstained is True
    assert answer.abstention_reason == (
        "INSUFFICIENT_CONFIDENCE: Evidence confidence falls below the reliability threshold (0.30)."
    )
    assert answer.text == ""
    assert answer.evidence == []
    actions = [step.action for step in answer.trace.steps]
    assert actions == [
        "request_received",
        "asset_received",
        "asset_ingestion_started",
        "asset_ingested",
        "routing_started",
        "route_selected",
        "vqa_started",
        "internvl_inference_started",
        "internvl_inference_completed",
        "verification_started",
        "verification_completed",
        "evidence_created",
        "response_completed",
    ]
    verification_step = next(
        step for step in answer.trace.steps if step.action == "verification_completed"
    )
    route_step = next(step for step in answer.trace.steps if step.action == "route_selected")
    assert route_step.params["tool"] == "vqa_grounding"
    assert verification_step.params["status"] == "abstained"
    assert verification_step.params["retained_evidence_count"] == 0
