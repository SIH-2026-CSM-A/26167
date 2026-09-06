"""InternVL adapter tests that avoid downloading model weights."""

from types import SimpleNamespace
from typing import Any

import torch
from PIL import Image
from transformers import PretrainedConfig, PreTrainedModel
from transformers.modeling_outputs import CausalLMOutputWithPast

from app.models import InternVL2Adapter, prepare_pixel_values


class TinyLegacyLanguageModel(PreTrainedModel):
    """Exercise real generation using tiny parameters and legacy generation hooks."""

    def __init__(self) -> None:
        """Create a small CPU model without GenerationMixin, like the upstream class."""
        super().__init__(
            PretrainedConfig(vocab_size=4, bos_token_id=1, eos_token_id=3, num_hidden_layers=1)
        )
        self.embedding = torch.nn.Embedding(4, 4)
        self.output = torch.nn.Linear(4, 4)

    def prepare_inputs_for_generation(self, input_ids, **kwargs):
        """Preserve the upstream-style input preparation hook during adaptation."""
        return {"input_ids": input_ids}

    def forward(self, input_ids, **kwargs):
        """Return real logits computed from the preserved parameters."""
        return CausalLMOutputWithPast(logits=self.output(self.embedding(input_ids)))


def test_adapter_prepares_actual_nested_language_model_without_global_mutation(monkeypatch):
    """The loaded nested instance must generate even when dynamic lookup returns another class."""
    import transformers
    import transformers.dynamic_module_utils as dynamic

    nested = TinyLegacyLanguageModel().eval()
    untouched = TinyLegacyLanguageModel()
    original_class = type(nested)
    original_generate = getattr(original_class, "generate", None)
    original_prepare = original_class.prepare_inputs_for_generation
    parameter = nested.embedding.weight
    config = nested.config
    outer = torch.nn.Module()
    outer.language_model = nested
    unrelated_class = type("SeparatelyLoadedLanguageModel", (TinyLegacyLanguageModel,), {})
    monkeypatch.setattr(
        dynamic, "get_class_from_dynamic_module", lambda *args, **kwargs: unrelated_class
    )
    monkeypatch.setattr(transformers.AutoModel, "from_pretrained", lambda *args, **kwargs: outer)
    monkeypatch.setattr(
        transformers.AutoTokenizer, "from_pretrained", lambda *args, **kwargs: SimpleNamespace()
    )

    adapter = InternVL2Adapter(device="cpu")
    adapter._ensure_loaded()

    assert callable(getattr(adapter._model.language_model, "generate", None))
    assert nested.can_generate()
    assert nested.embedding.weight is parameter
    assert nested.config is config
    assert nested.device.type == "cpu"
    assert nested.dtype == parameter.dtype
    assert type(nested) is not original_class
    assert type(untouched) is original_class
    assert untouched.prepare_inputs_for_generation.__func__ is original_prepare
    assert getattr(original_class, "generate", None) is original_generate
    assert torch.equal(
        nested.prepare_inputs_for_generation(torch.tensor([[1, 2]]))["input_ids"],
        torch.tensor([[1, 2]]),
    )
    generated = nested.generate(
        torch.tensor([[1, 2]]), max_new_tokens=2, do_sample=False, use_cache=False
    )
    assert generated.shape[0] == 1
    assert 2 < generated.shape[1] <= 4


def test_generation_compatibility_preserves_existing_generation_interface():
    """Already capable models retain their class, generation method and configuration."""
    from app.models.internvl import _prepare_language_model_generation

    existing_config = object()
    nested = SimpleNamespace(generate=str, generation_config=existing_config)
    original_class = type(nested)

    _prepare_language_model_generation(SimpleNamespace(language_model=nested))

    assert type(nested) is original_class
    assert nested.generate is str
    assert nested.generation_config is existing_config


def test_generation_preserves_legacy_tuple_cache_across_decoding_steps():
    """A legacy input hook must receive tuple caches rather than a new DynamicCache."""
    from app.models.internvl import _prepare_language_model_generation

    class TupleCacheLanguageModel(TinyLegacyLanguageModel):
        """Model the tuple-cache contract used by the cached InternLM2 source."""

        def prepare_inputs_for_generation(self, input_ids, past_key_values=None, **kwargs):
            """Use the existing tuple cache to select only unprocessed tokens."""
            if past_key_values is not None:
                input_ids = input_ids[:, past_key_values[0][0].shape[2] :]
            return {"input_ids": input_ids, "past_key_values": past_key_values}

        def forward(self, input_ids, past_key_values=None, **kwargs):
            """Compute logits and return the growing tuple cache expected by this model."""
            past_length = 0 if past_key_values is None else past_key_values[0][0].shape[2]
            cache = torch.zeros(1, 1, past_length + input_ids.shape[1], 1)
            return CausalLMOutputWithPast(
                logits=self.output(self.embedding(input_ids)), past_key_values=((cache, cache),)
            )

    nested = TupleCacheLanguageModel().eval()
    with torch.no_grad():
        nested.output.weight.zero_()
        nested.output.bias.zero_()
        nested.output.bias[2] = 1
    _prepare_language_model_generation(SimpleNamespace(language_model=nested))

    generated = nested.generate(
        torch.tensor([[1, 2]]), max_new_tokens=2, do_sample=False, use_cache=True
    )

    assert generated.tolist() == [[1, 2, 2, 2]]


def test_generation_aligns_stale_position_ids_during_cached_decoding():
    """During cached decoding, position_ids must be aligned to the current input token."""
    from app.models.internvl import _prepare_language_model_generation

    class PositionIdCheckingModel(TinyLegacyLanguageModel):
        """Model that checks position_ids shape matches input_ids during forward passes."""

        def __init__(self) -> None:
            super().__init__()
            self.forward_calls: list[dict[str, Any]] = []

        def prepare_inputs_for_generation(
            self, input_ids, past_key_values=None, position_ids=None, **kwargs
        ):
            """Accept position_ids in kwargs without slicing, like upstream InternLM2."""
            if past_key_values is not None:
                input_ids = input_ids[:, -1:]
            return {
                "input_ids": input_ids,
                "past_key_values": past_key_values,
                "position_ids": position_ids,
            }

        def forward(self, input_ids, past_key_values=None, position_ids=None, **kwargs):
            self.forward_calls.append(
                {
                    "input_len": input_ids.shape[1],
                    "pos_len": position_ids.shape[1] if position_ids is not None else None,
                }
            )
            # Rotary embedding raises if position_ids length exceeds input length during decode
            if past_key_values is not None and position_ids is not None:
                if position_ids.shape[1] != input_ids.shape[1]:
                    msg = (
                        f"Position IDs length {position_ids.shape[1]} "
                        f"must match input length {input_ids.shape[1]}"
                    )
                    raise ValueError(msg)
            past_length = 0 if past_key_values is None else past_key_values[0][0].shape[2]
            cache = torch.zeros(1, 1, past_length + input_ids.shape[1], 1)
            return CausalLMOutputWithPast(
                logits=self.output(self.embedding(input_ids)), past_key_values=((cache, cache),)
            )

    nested = PositionIdCheckingModel().eval()
    with torch.no_grad():
        nested.output.weight.zero_()
        nested.output.bias.zero_()
        nested.output.bias[2] = 1
    _prepare_language_model_generation(SimpleNamespace(language_model=nested))

    # Test direct prepare_inputs_for_generation contract
    stale_pos = torch.arange(5).unsqueeze(0)
    prepared = nested.prepare_inputs_for_generation(
        torch.tensor([[2]]), past_key_values=((torch.zeros(1, 1, 4, 1),),), position_ids=stale_pos
    )
    assert prepared["input_ids"].shape == (1, 1)
    assert prepared["position_ids"].shape == (1, 1)
    assert prepared["position_ids"].item() == 4

    # Execute full autoregressive generation across at least two decode steps
    generated = nested.generate(
        torch.tensor([[1, 2]]), max_new_tokens=3, do_sample=False, use_cache=True
    )
    assert generated.tolist() == [[1, 2, 2, 2, 2]]
    assert len(nested.forward_calls) >= 3
    for call in nested.forward_calls[1:]:
        assert call["input_len"] == 1
        if call["pos_len"] is not None:
            assert call["pos_len"] == 1


def test_adapter_is_lazy_until_generation() -> None:
    """Constructing the adapter must not initialize or download the model."""
    adapter = InternVL2Adapter()

    assert adapter.is_loaded is False
    assert adapter.model_id == "OpenGVLab/InternVL2-2B"


def test_prepare_pixel_values_returns_model_tensor() -> None:
    """A model-ready RGB image must become a normalized 448px tensor batch."""
    image = Image.new("RGB", (12, 8), color=(20, 80, 140))

    pixels = prepare_pixel_values(image)

    assert tuple(pixels.shape) == (1, 3, 448, 448)
    assert pixels.dtype.is_floating_point


def test_windows_cpu_safetensors_compat_changes_mmap_to_pread(monkeypatch) -> None:
    """On Windows CPU, mmap must be redirected to pread."""
    monkeypatch.setattr("sys.platform", "win32")

    import safetensors
    import safetensors.torch as safetensors_torch
    import transformers.modeling_utils as mu

    from app.models import windows_cpu_safetensors_compat

    captured_kwargs: dict = {}

    def dummy_safe_open(filename, *args, **kwargs):
        captured_kwargs.update(kwargs)
        return "dummy_handle"

    monkeypatch.setattr(safetensors, "safe_open", dummy_safe_open)
    monkeypatch.setattr(safetensors_torch, "safe_open", dummy_safe_open)
    monkeypatch.setattr(mu, "safe_open", dummy_safe_open)

    with windows_cpu_safetensors_compat("cpu"):
        safetensors_torch.safe_open(
            "test.safetensors", framework="pt", device="cpu", backend="mmap"
        )

    assert captured_kwargs.get("backend") == "pread"


def test_windows_cpu_safetensors_compat_preserves_non_windows_or_non_cpu(monkeypatch) -> None:
    """On non-Windows or non-CPU, the requested backend is preserved untouched."""
    import safetensors
    import transformers.modeling_utils as mu

    from app.models import windows_cpu_safetensors_compat

    captured_kwargs: dict = {}

    def dummy_safe_open(filename, *args, **kwargs):
        captured_kwargs.update(kwargs)
        return "dummy_handle"

    monkeypatch.setattr(safetensors, "safe_open", dummy_safe_open)
    monkeypatch.setattr(mu, "safe_open", dummy_safe_open)

    # Test Linux CPU
    monkeypatch.setattr("sys.platform", "linux")
    with windows_cpu_safetensors_compat("cpu"):
        mu.safe_open("test.safetensors", framework="pt", device="cpu", backend="mmap")
    assert captured_kwargs.get("backend") == "mmap"

    # Test Windows CUDA
    monkeypatch.setattr("sys.platform", "win32")
    captured_kwargs.clear()
    with windows_cpu_safetensors_compat("cuda:0"):
        mu.safe_open("test.safetensors", framework="pt", device="cuda:0", backend="mmap")
    assert captured_kwargs.get("backend") == "mmap"


def test_windows_cpu_safetensors_compat_restoration(monkeypatch) -> None:
    """Original safe_open references must be restored on exit and on error."""
    monkeypatch.setattr("sys.platform", "win32")

    import safetensors
    import safetensors.torch as safetensors_torch
    import transformers.modeling_utils as mu

    from app.models import windows_cpu_safetensors_compat

    orig_mu = mu.safe_open
    orig_st = safetensors.safe_open
    orig_st_torch = safetensors_torch.safe_open

    with windows_cpu_safetensors_compat("cpu"):
        assert mu.safe_open != orig_mu
        assert safetensors_torch.safe_open != orig_st_torch

    assert mu.safe_open == orig_mu
    assert safetensors.safe_open == orig_st
    assert safetensors_torch.safe_open == orig_st_torch

    # Test restoration on exception
    try:
        with windows_cpu_safetensors_compat("cpu"):
            assert mu.safe_open != orig_mu
            raise ValueError("simulated loading error")
    except ValueError:
        pass

    assert mu.safe_open == orig_mu
    assert safetensors.safe_open == orig_st
    assert safetensors_torch.safe_open == orig_st_torch
