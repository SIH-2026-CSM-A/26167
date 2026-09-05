## 2026-09-05 — YASH-001: Core Contracts & Core Config

Built via Claude Code (single-agent, Ubuntu).

**Did:** app.contracts (QueryRequest, ImageInput, Modality, Evidence, EvidenceType,
TraceStep, ExecutionTrace, Answer), app.core (config.py w/ cost_ceiling hard stop,
db.py async SQLAlchemy session, logging.py), initial Alembic scaffold, one test file
per module.

**Rejected along the way:**
- First pass on Evidence.type was a free str — rejected because it lets every
  consumer (frontend, report generator, conflict resolution) silently drift on
  spelling for a value the spec (§2.7) actually enumerates. Replaced with
  EvidenceType StrEnum.
- First pass on Answer had no abstention field at all — inferred from empty
  evidence. Rejected per F15/F16: abstention has to be explicit and typed, not
  inferred downstream. Added abstained + abstention_reason with a validator
  linking them.
- schemas.py docstring initially copied the 26034 repo's "only the contracts lead
  edits this" ownership line from an unrelated AGENTS.md convention. Removed —
  26167 has one owner, no such split exists here.
- Initial config.py docstring cited AGENTS.md's "Cost ceilings" section before
  verifying that section actually existed in this repo's AGENTS.md. Verified
  (line 54) before keeping the citation.

**Checks:** ruff check / ruff format --check / lint-imports / pytest — all green,
15 passed.

## 2026-09-05 — YASH-002: Pipeline & API Skeleton

Built via Claude Code (single-agent, Ubuntu).

**Did:** app.pipeline (Stage Protocol + 5 stub implementations — ingestion, router,
tool, verification, evidence — each docstring-marked as the seam for its real
module; pipeline.run() chaining all five, building a real ExecutionTrace),
app.api (POST /query, multipart file+query+per-image-modality, thin, delegates to
pipeline.run()), one test file per new module.

**Rejected along the way:**
- Considered creating placeholder files inside the four other owners' directories
  (ingestion/, router/, tools/, verification/, evidence/) so pipeline could do real
  imports from day one. Rejected — crosses CODEOWNERS boundaries into paths not
  owned by this ticket. Used internal stub stages inside app.pipeline instead,
  each documented as the seam to swap for a real import once that module lands.
- Before touching pyproject.toml over a suspected layers-contract bug, created
  two throwaway `_probe.py` files (one in app/pipeline, one in app/api, with api
  importing pipeline) and ran `uv run lint-imports` against them first. The raw
  output came back BROKEN — "app.api is not allowed to import app.pipeline:
  app.api._probe -> app.pipeline._probe (l.1)" — confirming app.pipeline was
  genuinely listed above app.api in the layers list (layers run highest to
  lowest, and only the higher layer may import the lower one). Only after
  reading that raw output was the issue raised, and only after user
  confirmation was the swap made. Probe files deleted once main.py/pipeline.py/
  stages.py existed and the real gate ran clean.

**Out-of-scope touches, both required and both flagged before making:**
- pyproject.toml: added python-multipart>=0.0.12 (required for POST /query's
  multipart parsing to work at all)
- pyproject.toml: swapped app.api above app.pipeline in the "Only pipeline
  composes modules" layers contract — the original order made api→pipeline
  imports illegal, contradicting ARCHITECTURE.md's own data flow and this
  ticket's whole point

**Checks:** ruff check / ruff format --check / lint-imports / pytest — all green,
20 passed.
