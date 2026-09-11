"""Spatial (bbox) grounding tests for the VQA tool (AASH-005)."""

from pathlib import Path

import numpy as np
import pytest
import rasterio
from PIL import Image

from app.tools.vqa_grounding import execute_vqa
from app.tools.vqa_grounding.tool import (
    BOX_TAG_PATTERN,
    _otsu_fallback_bbox,
    _parse_native_bbox,
)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures"
S2HAND_PATH = FIXTURES_DIR / "Bolivia_103757_S2Hand.tif"


def _load_real_rgb_image() -> Image.Image:
    """Real Sen1Floods11 Bolivia S2Hand scene as an RGB PIL image (B4/B3/B2, 2-98% stretch).

    Band order per the fixture's own README and test_fusion_cloud_detector.py's
    documented reading: B1..B7,B8,B8A,B9,B10,B11,B12 (13 bands), so red=index 3,
    green=index 2, blue=index 1.
    """
    with rasterio.open(S2HAND_PATH) as src:
        arr = src.read()
    rgb = np.moveaxis(arr[[3, 2, 1]].astype(np.float32), 0, -1)
    low, high = np.percentile(rgb, 2), np.percentile(rgb, 98)
    stretched = np.clip((rgb - low) / (high - low), 0, 1) * 255
    return Image.fromarray(stretched.astype(np.uint8), mode="RGB")


class _FakeGroundingModel:
    """Discriminates by prompt content, unlike DeterministicVqaModel's two-way split."""

    model_id = "test/fake-grounding"
    device = "test"
    active_model_identity = None

    def __init__(self, answer: str, bbox_response: str) -> None:
        self._answer = answer
        self._bbox_response = bbox_response

    def generate(self, image: Image.Image, prompt: str) -> str:
        assert image.mode == "RGB"
        if "<ref>" in prompt:
            return self._bbox_response
        if "Candidate answer:" in prompt:
            return "- " + self._answer
        return self._answer


@pytest.fixture(scope="module")
def real_image() -> Image.Image:
    if not S2HAND_PATH.exists():
        pytest.skip(f"real Sen1Floods11 S2Hand fixture not present at {S2HAND_PATH}")
    return _load_real_rgb_image()


def test_bbox_not_triggered_without_spatial_language(real_image: Image.Image) -> None:
    """A non-spatial question must never spend a bbox-grounding model call."""
    model = _FakeGroundingModel(
        answer="A river is visible.",
        bbox_response="<ref>river</ref><box>[[100,200,300,400]]</box>",
    )

    result = execute_vqa(
        image=real_image,
        question="What geographic feature is visible?",
        source_asset_id="asset-1",
        model=model,
    )

    assert result.bbox is None
    assert result.bbox_source is None


@pytest.mark.parametrize("trigger", ["highlight", "locate", "where", "point out", "HIGHLIGHT"])
def test_native_bbox_parsed_and_scaled_on_real_image(real_image: Image.Image, trigger: str) -> None:
    """A well-formed native <box> is parsed and scaled from InternVL's 0-1000 space."""
    model = _FakeGroundingModel(
        answer="The flooded area is near the river.",
        bbox_response="<ref>flooded area</ref><box>[[100,200,300,400]]</box>",
    )

    result = execute_vqa(
        image=real_image,
        question=f"Can you {trigger} the flooded area?",
        source_asset_id="asset-1",
        model=model,
    )

    width, height = real_image.size
    assert result.bbox_source == "internvl_native"
    assert result.bbox == [
        round(100 / 1000 * width),
        round(200 / 1000 * height),
        round(300 / 1000 * width),
        round(400 / 1000 * height),
    ]
    assert result.bbox_label == result.raw_answer


def test_malformed_native_box_falls_back_to_otsu_on_real_image(real_image: Image.Image) -> None:
    """No parseable <box> on a real image with actual structure falls back to Otsu."""
    model = _FakeGroundingModel(
        answer="The flooded area is near the river.",
        bbox_response="I cannot determine exact coordinates.",
    )

    result = execute_vqa(
        image=real_image,
        question="Where is the flooded area?",
        source_asset_id="asset-1",
        model=model,
    )

    assert result.bbox_source == "otsu_fallback"
    assert result.bbox is not None
    x1, y1, x2, y2 = result.bbox
    width, height = real_image.size
    assert 0 <= x1 < x2 <= width
    assert 0 <= y1 < y2 <= height


def test_multiple_boxes_are_rejected_not_guessed(real_image: Image.Image) -> None:
    """More than one candidate box must not be silently resolved to one."""
    model = _FakeGroundingModel(
        answer="Two rivers are visible.",
        bbox_response=(
            "<ref>river one</ref><box>[[10,10,50,50]]</box>"
            "<ref>river two</ref><box>[[60,60,90,90]]</box>"
        ),
    )

    result = execute_vqa(
        image=real_image,
        question="Locate the rivers.",
        source_asset_id="asset-1",
        model=model,
    )

    assert result.bbox_source == "otsu_fallback"


def test_both_paths_fail_on_uniform_image_returns_no_bbox() -> None:
    """A featureless image has no Otsu-separable region; a malformed box has none either.

    Deliberately synthetic and uniform here (not the real fixture): this proves the
    "no fabricated coordinates" contract for the case where no real spatial signal
    exists at all, which a real photograph cannot exercise deterministically.
    """
    uniform_image = Image.new("RGB", (64, 64), color=(120, 120, 120))
    model = _FakeGroundingModel(answer="Nothing distinct is visible.", bbox_response="")

    result = execute_vqa(
        image=uniform_image,
        question="Where is the anomaly?",
        source_asset_id="asset-1",
        model=model,
    )

    assert result.bbox is None
    assert result.bbox_source is None


def test_parse_native_bbox_rejects_zero_area_box() -> None:
    """A degenerate box (x2<=x1 or y2<=y1) must not be reported as real geometry."""
    assert _parse_native_bbox("<box>[[100,100,100,400]]</box>", (512, 512)) is None
    assert _parse_native_bbox("<box>[[100,400,300,400]]</box>", (512, 512)) is None


def test_parse_native_bbox_rejects_empty_output() -> None:
    assert _parse_native_bbox("", (512, 512)) is None


def test_box_tag_pattern_matches_documented_internvl_format() -> None:
    """Sanity-check the regex against InternVL's own documented output shape."""
    assert BOX_TAG_PATTERN.findall("<ref>car</ref><box>[[75,658,250,871]]</box>") == [
        ("75", "658", "250", "871")
    ]


def test_otsu_fallback_returns_none_on_uniform_array() -> None:
    assert _otsu_fallback_bbox(Image.new("RGB", (32, 32), color=(10, 10, 10))) is None
