"""Lazy local InternVL3-2B adapter for one RGB image and one prompt."""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from collections.abc import Iterator
from typing import Any

import numpy as np
import torch
from PIL import Image

DEFAULT_MODEL_ID = "OpenGVLab/InternVL3-2B"
MODEL_INPUT_SIZE = 448
MAX_NEW_TOKENS = 128
IMAGENET_MEAN = np.asarray((0.485, 0.456, 0.406), dtype=np.float32)
IMAGENET_STD = np.asarray((0.229, 0.224, 0.225), dtype=np.float32)
GENERATION_COMPAT_MARKER = "_satquery_generation_compatible"


class InternVLModelError(RuntimeError):
    """Raised when local model initialization or inference cannot complete."""


@contextlib.contextmanager
def windows_cpu_safetensors_compat(device: str | torch.device) -> Iterator[None]:
    """Redirect safetensors mmap to pread for Windows CPU model loading.

    Windows mmap on multi-gigabyte safetensors checkpoints triggers native access
    violations in torch_cpu.dll during tensor materialization. Replacing mmap with
    pread avoids the memory-mapping commit crash on Windows CPU while preserving
    normal behavior on Linux/macOS and non-CPU devices.
    """
    dev_str = str(device).lower().strip()
    is_windows_cpu = (sys.platform == "win32") and ("cpu" in dev_str)
    if not is_windows_cpu:
        yield
        return

    import safetensors
    import safetensors.torch as safetensors_torch
    import transformers.modeling_utils as mu

    orig_mu_safe_open = getattr(mu, "safe_open", None)
    orig_st_safe_open = getattr(safetensors, "safe_open", None)
    orig_st_torch_safe_open = getattr(safetensors_torch, "safe_open", None)

    def compat_safe_open(filename: str | os.PathLike[Any], *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("backend") == "mmap" or "backend" not in kwargs:
            kwargs["backend"] = "pread"
        target_fn = orig_st_safe_open or orig_mu_safe_open
        if target_fn is None:
            raise RuntimeError("safetensors.safe_open is not available")
        return target_fn(filename, *args, **kwargs)

    try:
        if orig_mu_safe_open is not None:
            mu.safe_open = compat_safe_open  # type: ignore[assignment]
        if orig_st_safe_open is not None:
            safetensors.safe_open = compat_safe_open  # type: ignore[assignment]
        if orig_st_torch_safe_open is not None:
            safetensors_torch.safe_open = compat_safe_open  # type: ignore[assignment]
        yield
    finally:
        if orig_mu_safe_open is not None:
            mu.safe_open = orig_mu_safe_open  # type: ignore[assignment]
        if orig_st_safe_open is not None:
            safetensors.safe_open = orig_st_safe_open  # type: ignore[assignment]
        if orig_st_torch_safe_open is not None:
            safetensors_torch.safe_open = orig_st_torch_safe_open  # type: ignore[assignment]


def prepare_pixel_values(image: Image.Image) -> torch.Tensor:
    """Apply the model card's RGB resize and ImageNet normalization on one image."""
    if not isinstance(image, Image.Image):
        raise TypeError("image must be a PIL Image")
    rgb_image = image.convert("RGB")
    resized = rgb_image.resize(
        (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), resample=Image.Resampling.BICUBIC
    )
    pixels = np.asarray(resized, dtype=np.float32) / 255.0
    normalized = (pixels - IMAGENET_MEAN) / IMAGENET_STD
    channels_first = np.ascontiguousarray(np.moveaxis(normalized, -1, 0))
    return torch.from_numpy(channels_first).unsqueeze(0)


def _prepare_language_model_generation(model: Any) -> None:
    """Restore the complete generation interface on this nested instance only."""
    language_model = model.language_model
    original_class = type(language_model)
    if getattr(original_class, GENERATION_COMPAT_MARKER, False):
        return

    from transformers import GenerationConfig
    from transformers.generation import GenerationMixin

    has_generation = callable(getattr(language_model, "generate", None))
    has_input_hook = callable(getattr(language_model, "prepare_inputs_for_generation", None))
    if has_generation and not has_input_hook:
        return
    if not has_input_hook:
        raise InternVLModelError("The nested language model has no generation input hook")

    class LegacyGenerationMixin(GenerationMixin):
        """Let InternLM2's existing input hook manage its legacy tuple cache."""

        @classmethod
        def _supports_default_dynamic_cache(cls) -> bool:
            """Prevent Transformers from injecting an incompatible DynamicCache."""
            return False

    orig_prepare = original_class.prepare_inputs_for_generation

    def prepare_inputs_for_generation(
        self: Any,
        input_ids: Any,
        past_key_values: Any = None,
        attention_mask: Any = None,
        inputs_embeds: Any = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Wrap InternLM2 input preparation to align stale position_ids on decode steps."""
        model_inputs = orig_prepare(
            self,
            input_ids,
            past_key_values=past_key_values,
            attention_mask=attention_mask,
            inputs_embeds=inputs_embeds,
            **kwargs,
        )
        if (
            model_inputs.get("past_key_values") is not None
            and model_inputs.get("position_ids") is not None
        ):
            pos_ids = model_inputs["position_ids"]
            active_inputs = model_inputs.get("input_ids")
            if active_inputs is None:
                active_inputs = model_inputs.get("inputs_embeds")
            if active_inputs is not None and pos_ids.shape[-1] > active_inputs.shape[-1]:
                model_inputs["position_ids"] = pos_ids[:, -active_inputs.shape[-1] :]
        return model_inputs

    # Dynamic imports can reload a class without updating the chat module's binding.
    # Adapt the actual instance, keeping upstream hooks ahead of mixin defaults.
    compatible_bases = (
        (original_class,) if has_generation else (original_class, LegacyGenerationMixin)
    )
    dynamic_cache_support = LegacyGenerationMixin._supports_default_dynamic_cache
    compatible_class = type(
        f"{original_class.__name__}WithGenerationMixin",
        compatible_bases,
        {
            "__module__": __name__,
            GENERATION_COMPAT_MARKER: True,
            "_supports_default_dynamic_cache": dynamic_cache_support,
            "prepare_inputs_for_generation": prepare_inputs_for_generation,
        },
    )
    language_model.__class__ = compatible_class
    if getattr(language_model, "generation_config", None) is None:
        language_model.generation_config = GenerationConfig.from_model_config(language_model.config)


class InternVLAdapter:
    """Load InternVL3-2B on first generation and expose its native chat inference."""

    def __init__(self, model_id: str = DEFAULT_MODEL_ID, device: str | None = None) -> None:
        """Configure model identity and execution device without loading weights."""
        if not model_id.strip():
            raise ValueError("model_id is required")
        self.model_id = model_id
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._dtype = (
            torch.bfloat16
            if torch.cuda.is_available() and torch.cuda.is_bf16_supported()
            else torch.float32
        )
        self._lock = threading.Lock()
        self._model: Any | None = None
        self._tokenizer: Any | None = None

    @property
    def is_loaded(self) -> bool:
        """Report whether weights and tokenizer have been initialized."""
        return self._model is not None and self._tokenizer is not None

    def generate(self, image: Image.Image, prompt: str) -> str:
        """Run real local InternVL chat generation for the supplied image and prompt."""
        if not prompt.strip():
            raise ValueError("prompt is required")
        self._ensure_loaded()
        pixel_values = prepare_pixel_values(image).to(device=self.device, dtype=self._dtype)
        question = f"<image>\n{prompt.strip()}"
        generation_config = {"max_new_tokens": MAX_NEW_TOKENS, "do_sample": False}
        try:
            with torch.inference_mode():
                response = self._model.chat(
                    self._tokenizer,
                    pixel_values,
                    question,
                    generation_config,
                )
        except Exception as error:
            raise InternVLModelError(f"InternVL3-2B inference failed: {error}") from error
        text = response[0] if isinstance(response, tuple) else response
        if not isinstance(text, str) or not text.strip():
            raise InternVLModelError("InternVL3-2B returned an empty response")
        return text.strip()

    def _ensure_loaded(self) -> None:
        """Initialize the exact configured model once, with CPU-compatible settings."""
        if self.is_loaded:
            return
        with self._lock:
            if self.is_loaded:
                return
            try:
                from transformers import AutoModel, AutoTokenizer
                from transformers.dynamic_module_utils import get_class_from_dynamic_module

                # Remote code omits this attribute on newer Transformers releases.
                chat_cls = get_class_from_dynamic_module(
                    "modeling_internvl_chat.InternVLChatModel", self.model_id
                )
                if not hasattr(chat_cls, "all_tied_weights_keys"):
                    chat_cls.all_tied_weights_keys = {}

                tokenizer = AutoTokenizer.from_pretrained(
                    self.model_id,
                    trust_remote_code=True,
                    use_fast=False,
                )
                with windows_cpu_safetensors_compat(self.device):
                    model = AutoModel.from_pretrained(
                        self.model_id,
                        torch_dtype=self._dtype,
                        low_cpu_mem_usage=True,
                        trust_remote_code=True,
                        use_safetensors=True,
                    )
                _prepare_language_model_generation(model)
                self._tokenizer = tokenizer
                self._model = model.eval().to(self.device)
            except Exception as error:
                self._model = None
                self._tokenizer = None
                raise InternVLModelError(f"InternVL3-2B initialization failed: {error}") from error
