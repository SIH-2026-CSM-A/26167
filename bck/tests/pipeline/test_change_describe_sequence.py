"""change_detection -> VQA sequence through pipeline.run(): order, handoff, trace, vetoes.

Real LEVIR-CD pair and real pipeline stages. The two models are stand-ins: BIT's remote
call returns a known probability map, and VQA uses the deterministic in-process model, so
the test can check exactly which region VQA was given.
"""

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import Modality
from app.db.models import Base
from app.inference.remote import RemoteChangeResult
from app.pipeline import PipelineError, PipelineUpload, run
from app.pipeline.pipeline import _MIN_CHANGE_CONTEXT_PX, _padded_region
from app.tools.change_detection.bit_io import encode_mask_png, encode_probability_png
from tests.helpers import DeterministicVqaModel

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
LEVIR_T1 = FIXTURES_DIR / "levir_test_1_t1.png"
LEVIR_T2 = FIXTURES_DIR / "levir_test_1_t2.png"
QUERY = "What changed between these dates, and what are the new structures in the changed area?"


@pytest.fixture(autouse=True)
def sqlite_db() -> Iterator[None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    with patch("app.db.session.get_sync_session_maker", return_value=session_maker):
        yield
    Base.metadata.drop_all(bind=engine)


class RecordingVqaModel(DeterministicVqaModel):
    """Deterministic VQA that also records the image size it was shown and when it ran."""

    def __init__(self, calls: list[str], sizes: list[tuple[int, int]]) -> None:
        super().__init__(answer="New houses.", grounding="New houses.")
        self._calls = calls
        self._sizes = sizes

    def generate(self, image: Image.Image, prompt: str) -> str:
        self._calls.append("vqa_grounding")
        self._sizes.append(image.size)
        return super().generate(image, prompt)


def _tiff(path: Path) -> bytes:
    buffer = BytesIO()
    Image.open(path).convert("RGB").save(buffer, format="TIFF")
    return buffer.getvalue()


def _uploads(*, with_post: bool = True, capture_order: bool = True) -> list[PipelineUpload]:
    uploads = [
        PipelineUpload(
            id="pre",
            filename="pre.tif",
            content_type="image/tiff",
            content=_tiff(LEVIR_T1),
            modality=Modality.OPTICAL,
            capture_order=0 if capture_order else None,
        )
    ]
    if with_post:
        uploads.append(
            PipelineUpload(
                id="post",
                filename="post.tif",
                content_type="image/tiff",
                content=_tiff(LEVIR_T2),
                modality=Modality.OPTICAL,
                capture_order=1 if capture_order else None,
            )
        )
    return uploads


def _bit_result(probability: np.ndarray, calls: list[str]):
    def fake_change_detect(pre, post):
        calls.append("change_detection")
        return RemoteChangeResult(
            probability_png=encode_probability_png(probability),
            mask_png=encode_mask_png(probability > 0.5),
            inference_seconds=0.2,
            total_seconds=0.25,
            model_identity={"base_model": "OpenGVLab/InternVL3-2B"},
        )

    return fake_change_detect


@pytest.fixture
def levir() -> None:
    if not LEVIR_T1.exists() or not LEVIR_T2.exists():
        pytest.skip(f"real LEVIR-CD fixtures not present under {FIXTURES_DIR}")


def test_sequence_runs_change_detection_then_vqa_on_the_largest_component(levir):
    probability = np.full((256, 256), 0.05, dtype=np.float32)
    # Largest: 60 x 50 = 3000 px (4.6% of the frame, above the confounder gate's 2.0% floor).
    probability[100:160, 60:110] = 0.95
    probability[10:20, 200:210] = 0.95  # smaller blob, must not be chosen
    calls: list[str] = []
    sizes: list[tuple[int, int]] = []

    with patch(
        "app.pipeline.pipeline.remote.change_detect", side_effect=_bit_result(probability, calls)
    ):
        answer = run(query=QUERY, uploads=_uploads(), model=RecordingVqaModel(calls, sizes))

    assert calls[0] == "change_detection"
    assert set(calls[1:]) == {"vqa_grounding"}

    steps = answer.trace.steps
    actions = [step.action for step in steps]
    route_step = next(step for step in steps if step.action == "route_selected")
    assert route_step.params["tool_sequence"] == ["change_detection", "vqa_grounding"]
    sequence = [
        (step.action, step.params.get("index"))
        for step in steps
        if step.action.startswith("sequence_")
    ]
    assert sequence == [
        ("sequence_step_started", 1),
        ("sequence_step_completed", 1),
        ("sequence_handoff", None),
        ("sequence_step_started", 2),
        ("sequence_step_completed", 2),
    ]
    assert actions.index("change_detection_started") < actions.index("sequence_handoff")
    assert actions.index("sequence_handoff") < actions.index("vqa_started")

    handoff = next(step for step in steps if step.action == "sequence_handoff")
    assert handoff.params["component_area_px"] == 3000
    assert handoff.params["component_bbox_mask_px"] == [60, 100, 110, 160]
    left, top, right, bottom = handoff.params["crop_box_px"]
    assert right - left >= _MIN_CHANGE_CONTEXT_PX and bottom - top >= _MIN_CHANGE_CONTEXT_PX
    assert left <= 60 and top <= 100 and right >= 110 and bottom >= 160  # contains component
    assert sizes and all(size == (right - left, bottom - top) for size in sizes)

    tools = {item.tool for item in answer.evidence}
    assert "change_detection.bit" in tools
    assert "internvl_vqa" in tools
    assert "In the largest changed region: New houses." in answer.text
    assert answer.confidence == pytest.approx(min(item.confidence for item in answer.evidence))


def test_no_changed_region_skips_vqa_and_says_so(levir):
    probability = np.full((256, 256), 0.05, dtype=np.float32)
    calls: list[str] = []
    with patch(
        "app.pipeline.pipeline.remote.change_detect", side_effect=_bit_result(probability, calls)
    ):
        answer = run(query=QUERY, uploads=_uploads(), model=RecordingVqaModel(calls, []))
    assert calls == ["change_detection"]
    short_circuit = next(s for s in answer.trace.steps if s.action == "sequence_short_circuit")
    assert short_circuit.params["skipped_tool"] == "vqa_grounding"
    assert "vqa_started" not in [step.action for step in answer.trace.steps]


@pytest.mark.parametrize(
    ("uploads_kwargs", "reason_code"),
    [
        ({"with_post": False}, "INSUFFICIENT_IMAGES"),
        ({"capture_order": False}, "TEMPORAL_ORDER_MISSING"),
    ],
)
def test_bad_inputs_are_vetoed_before_either_tool_runs(levir, uploads_kwargs, reason_code):
    calls: list[str] = []
    with patch(
        "app.pipeline.pipeline.remote.change_detect",
        side_effect=_bit_result(np.zeros((256, 256), dtype=np.float32), calls),
    ):
        with pytest.raises(PipelineError) as excinfo:
            run(query=QUERY, uploads=_uploads(**uploads_kwargs), model=RecordingVqaModel(calls, []))
    assert calls == []
    assert excinfo.value.status_code == 422
    assert excinfo.value.reason_code == reason_code
    actions = [step.action for step in excinfo.value.trace.steps]
    assert not any(
        action in actions
        for action in ("sequence_step_started", "change_detection_started", "vqa_started")
    )


@pytest.mark.parametrize(
    ("bbox", "image_size", "expected"),
    [
        ((60, 100, 90, 140), (256, 256), (11, 56, 139, 184)),  # centred growth to 128
        ((0, 0, 5, 5), (256, 256), (0, 0, 128, 128)),  # clamped at the top-left corner
        ((250, 250, 256, 256), (256, 256), (128, 128, 256, 256)),  # clamped at bottom-right
        ((10, 10, 20, 20), (100, 90), (0, 0, 100, 90)),  # image smaller than 128: whole image
        ((0, 0, 200, 20), (1024, 1024), (0, 0, 800, 128)),  # scaled 4x; only height padded
    ],
)
def test_padded_region(bbox, image_size, expected):
    assert _padded_region(bbox, mask_shape=(256, 256), image_size=image_size) == expected
