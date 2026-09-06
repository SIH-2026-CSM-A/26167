"""Runtime router tests for the supported single-image slice."""

from app.contracts import ImageInput, Modality, QueryRequest
from app.router import route_request


def test_single_image_visual_question_selects_internvl_vqa() -> None:
    """One image and a natural-language question must select the InternVL VQA tool."""
    request = QueryRequest(
        query="What major geographic features are visible?",
        images=[ImageInput(id="asset-1", modality=Modality.OPTICAL, format="GTiff")],
    )

    decision = route_request(request)

    assert decision.supported is True
    assert decision.intent == "vqa"
    assert decision.tool_name == "internvl_vqa"
    assert "single uploaded image" in decision.reason
