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
