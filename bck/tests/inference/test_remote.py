"""app.inference.remote against a mocked gradio_client: success, timeout, quota, connection."""

import base64
from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import numpy as np
import pytest
from gradio_client.exceptions import AppError
from PIL import Image

from app.core.config import get_settings
from app.inference import remote
from app.tools.change_detection.bit_io import (
    decode_mask_png,
    decode_probability_png,
    encode_mask_png,
    encode_probability_png,
)

IDENTITY = {"base_model": "OpenGVLab/InternVL3-2B", "adapter_name": "yash004-mlp1-vision-lora"}


@pytest.fixture(autouse=True)
def configured_space(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("INFERENCE_SPACE", "owner/satquery-inference")
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")
    monkeypatch.setenv("INFERENCE_TIMEOUT_S", "7")
    get_settings.cache_clear()
    remote._reset_client()
    remote._last_model_identity = None
    yield
    get_settings.cache_clear()
    remote._reset_client()
    remote._last_model_identity = None


def _job(result=None, error: Exception | None = None) -> MagicMock:
    job = MagicMock()
    if error is not None:
        job.result.side_effect = error
    else:
        job.result.return_value = result
    return job


def _vqa_payload() -> dict:
    return {
        "raw_answer": "A river crosses the scene.",
        "raw_grounding_output": "A river crosses the scene.",
        "raw_bbox_output": "<ref>river</ref><box>[[100,200,300,400]]</box>",
        "box_px": [45, 90, 134, 179],
        "image_size": [448, 448],
        "timings": {"answer_s": 1.5, "grounding_s": 2.5, "bbox_s": 0.5, "total_s": 4.6},
        "model_identity": IDENTITY,
    }


def test_vqa_ground_sends_the_image_as_a_png_file_and_parses_the_result():
    sent: dict = {}

    def submit(image_file, question, api_name):
        with Image.open(image_file["path"]) as image:
            sent.update(size=image.size, format=image.format, question=question, api=api_name)
        return _job(_vqa_payload())

    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.side_effect = submit
        result = remote.vqa_ground(Image.new("RGB", (448, 448), "blue"), "Where is the river?")

    client_cls.assert_called_once()
    assert client_cls.call_args.args == ("owner/satquery-inference",)
    assert client_cls.call_args.kwargs["hf_token"] == "hf_test_token"
    assert sent == {
        "size": (448, 448),
        "format": "PNG",
        "question": "Where is the river?",
        "api": "/vqa_ground",
    }
    assert result.raw_answer == "A river crosses the scene."
    assert (result.answer_seconds, result.grounding_seconds, result.bbox_seconds) == (1.5, 2.5, 0.5)
    assert remote.last_model_identity() == IDENTITY


def test_change_detect_decodes_mask_and_probability_within_quantization_bound():
    probability = np.random.default_rng(3).random((256, 256), dtype=np.float32)
    mask = probability > 0.5
    payload = {
        "probability_png_b64": base64.b64encode(encode_probability_png(probability)).decode(),
        "mask_png_b64": base64.b64encode(encode_mask_png(mask)).decode(),
        "stats": {"changed_pixel_count": int(mask.sum()), "changed_fraction": float(mask.mean())},
        "timings": {"preprocess_s": 0.01, "inference_s": 0.3, "total_s": 0.32},
        "model_identity": IDENTITY,
    }
    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.return_value = _job(payload)
        result = remote.change_detect(Image.new("RGB", (256, 256)), Image.new("RGB", (256, 256)))

    assert client_cls.return_value.submit.call_args.kwargs["api_name"] == "/change_detect"
    assert np.array_equal(decode_mask_png(result.mask_png), mask)
    assert np.abs(decode_probability_png(result.probability_png) - probability).max() <= 1 / 65535
    assert result.inference_seconds == 0.3


def test_timeout_cancels_the_job_and_raises_inference_unavailable():
    job = _job(error=TimeoutError())
    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.return_value = job
        with pytest.raises(remote.InferenceUnavailable, match="within 7 s"):
            remote.vqa_ground(Image.new("RGB", (448, 448)), "What is this?")
    job.result.assert_called_once_with(timeout=7)
    job.cancel.assert_called_once()


def test_quota_app_error_raises_quota_exceeded():
    # Only the word "quota" is relied on; the rest of this message is illustrative.
    error = AppError("You have exceeded your GPU quota. Try again later.")
    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.return_value = _job(error=error)
        with pytest.raises(remote.QuotaExceeded) as excinfo:
            remote.vqa_ground(Image.new("RGB", (448, 448)), "What is this?")
    assert excinfo.value.reason_code == "INFERENCE_QUOTA"


def test_other_app_errors_are_inference_unavailable():
    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.return_value = _job(error=AppError("CUDA out of memory"))
        with pytest.raises(remote.InferenceUnavailable):
            remote.vqa_ground(Image.new("RGB", (448, 448)), "What is this?")


def test_connection_error_is_retried_once_then_succeeds():
    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.side_effect = [
            httpx.ConnectError("connection refused"),
            _job(_vqa_payload()),
        ]
        result = remote.vqa_ground(Image.new("RGB", (448, 448)), "Where is the river?")
    assert result.raw_answer == "A river crosses the scene."
    assert client_cls.call_count == 2  # client rebuilt after the failed connection


def test_connection_error_twice_raises_inference_unavailable():
    with patch.object(remote, "Client") as client_cls:
        client_cls.return_value.submit.side_effect = httpx.ConnectError("connection refused")
        with pytest.raises(remote.InferenceUnavailable, match="unreachable"):
            remote.vqa_ground(Image.new("RGB", (448, 448)), "What is this?")
    assert client_cls.return_value.submit.call_count == 2


def test_client_creation_failure_is_inference_unavailable():
    with patch.object(remote, "Client", side_effect=ValueError("Could not fetch config")):
        with pytest.raises(remote.InferenceUnavailable, match="Could not fetch config"):
            remote.vqa_ground(Image.new("RGB", (448, 448)), "What is this?")


def test_not_configured_raises_without_contacting_anything(monkeypatch):
    monkeypatch.delenv("INFERENCE_SPACE")
    get_settings.cache_clear()
    with patch.object(remote, "Client") as client_cls:
        with pytest.raises(remote.InferenceUnavailable, match="INFERENCE_SPACE unset"):
            remote.vqa_ground(Image.new("RGB", (448, 448)), "What is this?")
    client_cls.assert_not_called()
    assert remote.is_configured() is False
