## 2026-09-05 — AASH-001/002: Env verification + dataset access

Built via Claude Code (single-agent, Ubuntu/WSL2). Run under Yashwanth's session, on
Yashwanth's request — not Aashritha's own session. Flagging per the Files-field note below.

**Files-field conflict (unresolved, needs Yashwanth to confirm/fix the ticket):**
Acceptance criterion 3 wants results in `session-log/aashritha.md`, but the ticket's Files
field only allows `bck/app/models/**` and `data/**`. `session-log/` isn't under either.
Wrote this file to `data/session-log/aashritha.md` as a stand-in so nothing outside the
Files field was touched. This is a workaround, not a fix — the ticket's Files field needs
correcting (or this location needs to become the real convention) before this is final.

### Environment
- GPU: NVIDIA GeForce RTX 4050 Laptop, 6141MiB total VRAM, driver 592.82, CUDA 13.1
  (via WSL2 passthrough — `lspci` doesn't see it directly, `nvidia-smi` does)
- Python (venv): 3.12.13
- Dependencies installed this session (via `uv pip install`, venv-only, pyproject.toml
  untouched): einops 0.8.2, sentencepiece 0.2.2, timm 1.0.29, torchvision 0.29.0
  (torch 2.14.0, transformers 5.16.1, accelerate 1.14.0, bitsandbytes 0.50.2 were already
  present from earlier tickets)
- `app.contracts` had no existing `ModelConfig`-like type (checked before writing one) —
  `VerifyConfig` dataclass defined locally in `verify_internvl2.py`, contracts untouched

### SEN12MS sample (Step 3) — BLOCKED
`https://mediatum.ub.tum.de/1474000` is a JS-rendered SPA. `curl`/`wget` against the parent
collection page and a child node both return only a generic shell page (`<title>mediaTUM -
Medien- und Publikationsserver</title>`), no real listing or file links reachable without a
browser executing JS. No placeholder image substituted, no other dataset swapped in.

### InternVL2-2B forward pass (Step 4) — BLOCKED on tokenizer load
Real weights/tokenizer downloaded from `https://huggingface.co/OpenGVLab/InternVL2-2B`
(unauthenticated, no HF_TOKEN set). Both the fp16 load path and the 4-bit bitsandbytes load
path fail identically at tokenizer construction:

```
RuntimeError: INTERNAL: piece must not include null character.
```

raised from `sentencepiece/__init__.py` inside `tokenization_internlm2.py`'s
`self.sp_model.Load(vocab_file)`. The downloaded `tokenizer.model` blob is a real 1.4MB
sentencepiece proto (verified by inspecting the cache — not a corrupted/zero-byte file or an
LFS pointer). This matches a known `sentencepiece>=0.2.0` regression: newer sentencepiece
rejects proto files containing literal null-byte pieces (byte-fallback tokens), which this
InternLM2-derived tokenizer's vocab uses. Installed sentencepiece here is 0.2.2. No downgrade
attempted — pinning a working version is a real fix, not a verification step, and wasn't
asked for.

Because the tokenizer never loads, no forward pass ran and there is no generated caption to
report — none fabricated. VRAM usage during the failed load: `nvidia-smi` shows 14MiB/6141MiB
(baseline, no process listed) — the failure happens before any weights move to GPU, so there
is no real "load VRAM" number to report beyond that baseline.

### Dataset access (Step 5)
- **BigEarthNet.txt** (arXiv:2603.29630) — confirmed-available.
  `https://huggingface.co/datasets/BIFOLD-BigEarthNetv2-0/BigEarthNet.txt`,
  gated:false, private:false, arxiv tag matches exactly (verified via HF search API and a
  direct HEAD request, HTTP 200).
- **VRSBench** — confirmed-available. Official GitHub `https://github.com/lx709/VRSBench`
  (HTTP 200) and HF mirror `https://huggingface.co/datasets/xiang709/VRSBench` (HTTP 200,
  gated:false).
- **RSVQA** — confirmed-available. Official site
  `http://rsvqa.sylvainlobry.com/` redirects (301) to
  `https://rsvqa.sylvainlobry.com/` (HTTP 200).
- **CDVQA** — confirmed-available. Official GitHub
  `https://github.com/YZHJessica/CDVQA` (HTTP 200) and HF mirror
  `https://huggingface.co/datasets/ljx620/CDVQA` (HTTP 200 on retry; first request hit a
  429 rate limit, not a real block).

**Checks:** not run — this ticket didn't touch `app.contracts`/`app.core`/pipeline/api, so
the four-gate command wasn't re-run for this change; `verify_internvl2.py` is a standalone
script, not covered by the existing test suite.

## 2026-09-05 (follow-up) — attempted fixes for both blockers, both genuinely failed

**Tokenizer fix attempt 1 — pin `sentencepiece==0.1.99`:** failed to install. No prebuilt
wheel for Python 3.12; building from source fails (`cmake`/`pkg-config` not found in this
environment) — `subprocess.CalledProcessError` from `./build_bundled.sh`. Did not install
build tooling to force it through; that's environment surgery beyond this ticket. Confirmed
`sentencepiece` is still 0.2.2 after the failed attempt.

**Tokenizer fix attempt 2 — patch the vocab proto in place:** ran the prescribed patch script
(after installing `protobuf`, which the script needs and wasn't present). It found and
rewrote `tokenizer.model`, reporting "patched 1 pieces" — exactly one piece contained a null
character. Reloading the tokenizer now fails with a *different* real error:
```
RuntimeError: INTERNAL: piece must not be empty.
```
The one patched piece was apparently just `"\x00"` alone, so stripping the null left an empty
string, which sentencepiece's proto validation also rejects. Re-ran `verify_internvl2.py`
end to end afterward — fp16 and 4-bit loads both still fail at tokenizer construction, this
new error, in both paths. No forward pass ran; no caption text exists to report. VRAM: still
16MiB/6141MiB baseline, no process — failure is still before anything reaches the GPU.

Both prescribed fixes now tried and both genuinely fail. Not improvising a third fix beyond
what was specified.

**SEN12MS rsync attempt:** `rsync rsync://m1474000@dataserv.ub.tum.de/m1474000/` with
`RSYNC_PASSWORD=1474000` → `@ERROR: auth failed on module m1474000` (exit 5). Also tried
`rsync://anonymous@dataserv.ub.tum.de/m1474000/` with an empty password — same auth failure.
A bare module listing (`rsync rsync://dataserv.ub.tum.de/`) succeeds (exit 0) but returns zero
modules. DNS for `dataserv.ub.tum.de` resolves fine (real host, not a typo/dead domain) — the
credentials as given just don't authenticate against this server. No file downloaded, nothing
fabricated in its place.

**Files-field fix:** done. `session-log/aashritha.md` (this file) now lives at
`session-log/aashritha.md`, moved via plain `mv` from `data/session-log/aashritha.md` — a
`git mv` wasn't possible because that path was never git-tracked (it's `data/`-gitignored,
discovered in the prior run). Ticket's Files field (`bck/app/models/**`, `data/**`) still
needs Yashwanth to add `session-log/**` — not done silently, flagging again here.

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
