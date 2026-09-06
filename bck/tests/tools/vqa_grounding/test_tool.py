"""VQA tool orchestration tests."""

from PIL import Image

from app.tools.vqa_grounding import execute_vqa
from tests.helpers import DeterministicVqaModel


def test_vqa_tool_runs_answer_and_grounding_passes_with_source_identity() -> None:
    """The tool must capture raw inference and grounded observations for verification."""
    model = DeterministicVqaModel(
        answer="A river is visible and pollution is present.",
        grounding="- A river is visible.\nUNSUPPORTED: pollution is present.",
    )

    result = execute_vqa(
        image=Image.new("RGB", (8, 8)),
        question="What is visible?",
        source_asset_id="asset-1",
        model=model,
    )

    assert result.source_asset_id == "asset-1"
    assert result.raw_answer == "A river is visible and pollution is present."
    assert result.supporting_observations == ("A river is visible.",)
    assert result.model_id == "test/deterministic-vqa"
    assert result.timing_seconds >= 0.0
