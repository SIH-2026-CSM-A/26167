## 2026-09-06 — ROHAN-002: BIT change detection tool — Rohan (Claude Code)

**Done**
- `app/tools/change_detection/detector.py`: Evidence-assembling entry
  point. Takes two `ImageInput`s, loads from `.path`, runs vendored BIT,
  returns `list[Evidence]`.
- BIT vendored into `bit_vendor/` (5 files, from `justchenhao/BIT_CD` @
  `adcd7aea6f234586ffffdd4e9959404f96271711` — verified against the local
  clone's actual git log; see `bit_vendor/VENDORED.md`).
- Verified against two real LEVIR-CD pairs: exact match on the all-zero
  no-change pair; IoU=0.8945/pixel accuracy=0.9548 on a real-change pair,
  cross-checked byte-for-byte against the original CLI run's saved output
  (identical changed-pixel fraction, 0.4132843017578125).
- All four gates green (`ruff check`, `ruff format --check`, `lint-imports`,
  `pytest` — 93 passed).

**Decided**
- Vendored only pure model-definition files to avoid new dependencies;
  detector.py reimplements load/forward/argmax directly, verified against
  `basic_model.py`'s actual source.
- `detector.py` builds `Evidence` directly, matching `fusion/reconcile.py`'s
  pattern — **`stub_tool` does not exist anywhere in this codebase.**
  `a04b865`'s commit message claims it was widened to `list[Evidence]`, but
  the actual diff never touches any such function, and a full-tree grep
  found zero matches. Flagging this so nobody else goes looking for it.

**Rejected**
- N/A this ticket — the open questions (ImageInput.path shape, stub_tool
  existence) were verification stops, not design rejections.

**Incomplete**
- Temp files at `ImageInput.path` are never cleaned up (known follow-up,
  not this ticket's scope).

Agent: Claude Code (Sonnet 5).
