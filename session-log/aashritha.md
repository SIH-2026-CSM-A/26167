
## AASH-001 — Colab, 2026-09-06

- Confirmed on fresh Colab (T4): InternVL2-2B tokenizer.model fails with
  `RuntimeError: INTERNAL: piece must not include null character` under
  sentencepiece 0.2.2 and transformers 5.16.1 — reproduces cross-environment,
  confirmed upstream bug, not local corruption or version-specific to prior
  machine.
- InternVL3-2B tokenizer loads clean under same sentencepiece 0.2.2.
- Model load required transformers pinned to 4.44.2 (5.16.1 breaks
  `_tied_weights_keys` API InternVL's custom modeling code expects), plus
  einops, timm.
- Full working stack: transformers==4.44.2, tokenizers==0.19.1,
  huggingface-hub==0.36.2, sentencepiece==0.2.2, einops==0.8.2, timm==1.0.29.
- **Decision: core VLM changed from InternVL2-2B to InternVL3-2B.**
  InternVL2-2B has no known fix; InternVL3-2B confirmed working, same
  family/size class.
- verify_internvl2.py deprecated, verify_internvl3.py renamed to
  verify_internvl.py.
- SEN12MS small sample: still open, not touched this session.

## AASH-001 — 4-bit verification, 2026-09-06

- InternVL3-2B confirmed working in 4-bit (bitsandbytes, nf4, double quant).
  Memory footprint: 2.22GB. Fits 6GB VRAM budget with room to spare.
- Required fix: device_map={"": 0} instead of "auto" — accelerate's
  dispatch_model calls .to() post-load, which bitsandbytes forbids on
  quantized models. Also required pinning accelerate==0.34.2 (default
  1.14.0 changed dispatch behavior, broke this even with correct device_map
  initially — pin, not just code fix, was the real cause).
- Remaining gap: no SEN12MS sample yet, so acceptance criterion 1 (real
  forward pass on real image) still open.

## AASH-001 — closed, 2026-09-06

- SEN12MS sample obtained via mespinosami/sen12mscr on HF (streaming, no
  full shard download). Saved to data/sen12ms_sample_s2.png,
  sen12ms_sample_s1.png.
- fp16 inference on real image produced degenerate output (repeated "!"
  tokens) — silent failure, no crash. Root cause: fp16 overflow in
  attention, no FlashAttention2 on this T4. Fixed by switching to bf16.
  Real coherent caption confirmed on the SEN12MS sample.
- 4-bit (bitsandbytes) load succeeds standalone (2.22GB footprint) but
  produces the SAME degenerate output as broken fp16 when given real image
  input — vision-tower quantization likely corrupting image features.
  4-bit is load-viable, NOT confirmed inference-viable. Flag for whoever
  builds the real VLM inference pipeline — don't assume 4-bit is safe
  without further testing.
- AASH-001 acceptance criteria: all four closed. Ticket marked done.
