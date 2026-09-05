
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
