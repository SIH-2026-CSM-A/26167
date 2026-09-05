# AGENTS.md
Read automatically by Antigravity, Codex, Claude Code, Cursor, Gemini CLI, Windsurf, Copilot.
These rules bind every agent on this repo, regardless of which one is running.

## What this project is
SatQuery AI — SIH26167 (ISRO/SAC). An agentic vision-language assistant for single, cross-modal
(optical+SAR), and bi-temporal remote-sensing imagery. Full architecture: `ARCHITECTURE.md`.
Full requirements: the six SatQuery AI docs in project knowledge (PSD/PRD/Features-Spec/
Technical-Implementation/Final-Master-Proposal/Research-And-References) — ask the team lead for
whichever one a ticket needs; do not assume its contents.

## Module ownership is absolute
See `.github/CODEOWNERS`. A module imports from `app.contracts`, `app.core`, and itself.
Nothing else. Two leaf modules never import each other. `app.pipeline` composes modules; modules
never compose each other. This is enforced by `import-linter` in CI
(`bck/pyproject.toml` → `[tool.importlinter]`) — a cross-module import fails the build before a
PR exists. If your ticket seems to need this, stop and say so; it's a ticket bug, not something
to work around.

## Contracts are not yours to change
Only the team lead (`ybaddam8-png`) edits `bck/app/contracts/`. Need a type or field that
doesn't exist there? Stop and ask on the ticket. Do not add it locally, do not define a
duplicate in your own module and hope it matches the real one later.

## Git protocol — not negotiable
- `git pull` before starting anything.
- One branch per ticket, cut from `main`, named exactly as the ticket's `Branch` field says.
- Never commit to `main`. Never merge your own work — the merge button is blocked for everyone
  except the lead.
- Commit incrementally, conventional-commits style (`feat:`, `fix:`, `refactor:`, `test:`,
  `docs:`, `chore:`). One large end-of-day commit is not acceptable — evaluators read commit
  history.
- Raise the PR yourself; the lead merges. After pushing, move the ticket to `review` in ClickUp.
- `session-log/<your-name>.md` before you finish a ticket — what you did, what you rejected and
  why, which agent you used. Never a shared file.

## Before any ticket is called done
```
cd bck && uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pytest
```
All four green. No exceptions.

## No fake data, no placeholders, no stubs
No TODO comments in shipped code. No invented rule number, statistic, threshold, or citation —
if a fact isn't in the Research-And-References doc, ask for it rather than asserting it. If
something can't be made real in the ticket's scope, cut it and say so in the PR description.

## When you're blocked
Don't sit silent. If you're stuck on something only the team lead can answer, say precisely
what you need, what you already checked, the options you see, and what you can keep building
in the meantime. Move the ClickUp ticket to `doubt` only if you genuinely cannot proceed on
anything.

## Cost ceilings (GenAI-specific)
No paid API call anywhere in the request path without a hard ceiling read from
`bck/app/core/config.py`. The only paid-API-adjacent call in this project is the optional
Bhashini voice input (P2) — it sits behind its own ceiling and is never on the critical demo
path. InternVL3-2B runs locally; there is no per-request quota to protect there because there's
no API call at all.

## Demo/offline constraint
The rehearsed demo runs against a locally cached dataset. No code path required for the demo may
depend on a live external fetch.
