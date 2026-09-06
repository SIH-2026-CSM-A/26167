from app.contracts import ImageInput, Modality, QueryRequest
from app.pipeline.pipeline import run


def test_run_reflects_actual_request_not_a_fixture():
    image = ImageInput(id="img-1", modality=Modality.OPTICAL, format="image/tiff", path="img-1.tif")
    request = QueryRequest(query="how many buildings are visible?", images=[image])

    answer = run(request)

    assert "how many buildings are visible?" in answer.text
    assert len(answer.evidence) == 1
    assert answer.evidence[0].payload["image_ids"] == ["img-1"]
    assert answer.abstained is False
    assert len(answer.trace.steps) == 4


def test_run_with_no_images_still_produces_an_answer():
    request = QueryRequest(query="hello")

    answer = run(request)

    assert answer.evidence[0].payload["image_ids"] == []
