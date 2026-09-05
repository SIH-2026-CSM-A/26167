# SKILLS.md — which Claude Code skill to invoke, and when

| Situation | Skill |
|---|---|
| Any repo structure, naming, branching, PR-standards question | `engineering-standards` |
| Touching InternVL2-2B, LoRA training, embeddings, or anything with a cost ceiling | `genai-project` |
| Anything user-facing in `fnt/` | `frontend-work` |
| Verifying a UI change in a real browser | `playwright-cli` |
| Understanding code you didn't write, before changing it | `explore-codebase` |
| Something broke and the cause isn't obvious | `debug-issue` |
| Changing working code without changing behavior | `refactor-safely` |
| Reviewing a diff before it's proposed as done | `review-changes` |
| Anything near auth, secrets, cost ceilings, or real data | `ship-safely` |
| Any README, pitch text, PR description a human outside the team reads | `writing-not-slop` |
| Non-trivial work of any kind, before writing code | `cplan` (plan mode, read-only) |

If a prompt into Claude Code doesn't name one of these where one applies, that's a miss — name
it explicitly in the prompt, don't wait for the agent to guess.
