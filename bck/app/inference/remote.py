"""Client for the SatQuery inference Space (VQA/grounding and BIT change detection).

Transport only: it sends already-preprocessed images as PNG files (gradio_client.handle_file)
and returns the Space's raw outputs. Resizing, decoding and evidence building stay with the
caller, so this module needs neither torch nor any tool module.
"""

from __future__ import annotations

import base64
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from gradio_client import Client, handle_file
from gradio_client.exceptions import AppError
from PIL import Image

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_CONNECTION_ERRORS = (httpx.TransportError, ConnectionError)
_client: Client | None = None
_client_lock = threading.Lock()
_last_model_identity: dict[str, Any] | None = None


class InferenceError(RuntimeError):
    """Base class: the inference Space could not produce a result."""

    reason_code = "INFERENCE_UNAVAILABLE"


class InferenceUnavailable(InferenceError):
    """Not configured, unreachable, timed out, or failed."""

    reason_code = "INFERENCE_UNAVAILABLE"


class QuotaExceeded(InferenceError):
    """The Space refused the call because the caller's GPU quota is used up (ZeroGPU)."""

    reason_code = "INFERENCE_QUOTA"


@dataclass(frozen=True)
class RemoteVqaResult:
    raw_answer: str
    raw_grounding_output: str
    raw_bbox_output: str | None
    answer_seconds: float
    grounding_seconds: float
    bbox_seconds: float | None
    total_seconds: float
    model_identity: dict[str, Any]


@dataclass(frozen=True)
class RemoteChangeResult:
    probability_png: bytes
    mask_png: bytes
    inference_seconds: float
    total_seconds: float
    model_identity: dict[str, Any]


def is_configured() -> bool:
    return bool(get_settings().inference_space)


def last_model_identity() -> dict[str, Any] | None:
    """Model identity reported by the most recent successful call in this process."""
    return _last_model_identity


def vqa_ground(image: Image.Image, question: str) -> RemoteVqaResult:
    """Run all VQA passes remotely on an image already at model input size."""
    with tempfile.TemporaryDirectory() as tmp:
        path = _write_png(image, Path(tmp) / "image.png")
        result = _call("/vqa_ground", handle_file(str(path)), question)
    timings = result["timings"]
    return RemoteVqaResult(
        raw_answer=result["raw_answer"],
        raw_grounding_output=result["raw_grounding_output"],
        raw_bbox_output=result["raw_bbox_output"],
        answer_seconds=timings["answer_s"],
        grounding_seconds=timings["grounding_s"],
        bbox_seconds=timings["bbox_s"],
        total_seconds=timings["total_s"],
        model_identity=result["model_identity"],
    )


def change_detect(pre: Image.Image, post: Image.Image) -> RemoteChangeResult:
    """Run BIT remotely on a pair already at BIT input size."""
    with tempfile.TemporaryDirectory() as tmp:
        pre_path = _write_png(pre, Path(tmp) / "pre.png")
        post_path = _write_png(post, Path(tmp) / "post.png")
        result = _call("/change_detect", handle_file(str(pre_path)), handle_file(str(post_path)))
    timings = result["timings"]
    return RemoteChangeResult(
        probability_png=base64.b64decode(result["probability_png_b64"]),
        mask_png=base64.b64decode(result["mask_png_b64"]),
        inference_seconds=timings["inference_s"],
        total_seconds=timings["total_s"],
        model_identity=result["model_identity"],
    )


def _write_png(image: Image.Image, path: Path) -> Path:
    image.save(path, format="PNG")
    return path


def _get_client() -> Client:
    global _client
    settings = get_settings()
    if not settings.inference_space:
        raise InferenceUnavailable("No inference Space is configured (INFERENCE_SPACE unset).")
    with _client_lock:
        if _client is None:
            _client = Client(
                settings.inference_space,
                hf_token=settings.hf_token,
                verbose=False,
                httpx_kwargs={"timeout": settings.inference_timeout_s},
            )
        return _client


def _reset_client() -> None:
    global _client
    with _client_lock:
        _client = None


def _call(api_name: str, *args: Any) -> dict[str, Any]:
    """Call one Space endpoint: one retry on connection errors, typed errors otherwise."""
    global _last_model_identity
    timeout = get_settings().inference_timeout_s
    for attempt in (1, 2):
        try:
            job = _get_client().submit(*args, api_name=api_name)
            try:
                result = job.result(timeout=timeout)
            except TimeoutError as error:
                job.cancel()
                raise InferenceUnavailable(
                    f"Inference Space did not answer {api_name} within {timeout} s."
                ) from error
        except InferenceError:
            raise
        except AppError as error:
            message = str(error)
            # ZeroGPU refuses over-quota calls with an app error whose message mentions the
            # quota; only that word is relied on, not the exact wording.
            if "quota" in message.lower():
                raise QuotaExceeded(f"Inference Space GPU quota exceeded: {message}") from error
            raise InferenceUnavailable(f"Inference Space error on {api_name}: {message}") from error
        except _CONNECTION_ERRORS as error:
            _reset_client()
            if attempt == 1:
                logger.warning("Inference Space connection failed (%s); retrying once.", error)
                continue
            raise InferenceUnavailable(f"Inference Space unreachable: {error}") from error
        except Exception as error:  # client creation (config fetch) and protocol failures
            _reset_client()
            raise InferenceUnavailable(f"Inference Space call failed: {error}") from error
        if not isinstance(result, dict):
            raise InferenceUnavailable(f"Unexpected {api_name} response type {type(result)}.")
        identity = result.get("model_identity")
        if isinstance(identity, dict):
            _last_model_identity = identity
        return result
    raise AssertionError("unreachable")
