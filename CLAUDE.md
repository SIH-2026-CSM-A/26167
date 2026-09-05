# Project: SatQuery AI (SIH26167)

## Stack
Python 3.11 / FastAPI / uv (backend, `bck/`). React + TypeScript + Vite + Tailwind + MapLibre
(frontend, `fnt/`). PostgreSQL with JSONB for evidence/trace. InternVL3-2B (LoRA-adapted) as the
core VLM. Full detail and rejected alternatives: `ARCHITECTURE.md`.

## Current phase
Scaffold just landed. No feature code exists yet. First real work starts once tickets are
written against the module map in `ARCHITECTURE.md` / `.github/CODEOWNERS`.

## Sprint goal
Round 1 (idea submission) deadline: **8 September 2026**. Critical-path order: vertical slice
(upload → routed answer → cited evidence) for one query type before anything else, then the
remaining mandatory PS capabilities, then domain adaptation logged as its own milestone, then
real benchmark numbers, then rehearsed demo.

## Project-specific rules
- **Gotchas that will cost an hour if missed:**
  - `InternVL3-2B` requires `trust_remote_code=True` in `transformers` — verify a working
    forward pass on day one, not day two.
  - The mandatory adaptation dataset is **BigEarthNet.txt** (arXiv:2603.29630) — not
    BigEarthNet-MM. They are different datasets; do not conflate them in code, data loaders, or
    a slide.
  - SAR imagery needs its own preprocessing (despeckle, calibrate DN→backscatter dB) before it
    touches any model. Never feed raw SAR DN values through an optical-trained encoder.
  - Pin dependency versions on day one. A mid-build `pip install -U` (or `uv sync` without a
    lockfile committed) changing `transformers` compatibility out from under the build is a real,
    avoidable risk.
- **Never** produce a numeric/spatial claim in an answer without a matching evidence-schema
  entry from an actual tool run — this is enforced in `verification/`, not left to the model's
  honesty.
- **Never** encode a rule, threshold, or benchmark figure from memory — cite the
  Research-And-References doc or ask for it.
- Use `cplan` for anything non-trivial — read-only plan mode before touching files.
