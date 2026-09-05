# TODO — SatQuery AI (SIH26167)

## Now
- [ ] Scaffold committed and pushed (this commit)
- [ ] Fill CODEOWNERS with real GitHub handles for Aashritha/Rohan/Shivasai/Likitha/Jashwanth —
      currently placeholders, review-routing is broken until this lands
- [ ] Branch protection ruleset + classic push restriction on `main` (lead, GitHub UI —
      see GITHUB-ORG-GUIDE.md)
- [ ] Merge settings: squash-only, merge/rebase off, auto-delete head branches (lead, GitHub UI)
- [ ] Claude GitHub App installed on `26167` specifically — org account, this repo only,
      OAuth credential, `@claude`-mention workflow only (decline the auto-review-every-PR one)
- [ ] First CI run — once green, add the check to the `main-protection` ruleset as a required
      status check (adding it before CI has run once blocks every PR forever)
- [ ] Vertical slice: upload → routed answer → cited evidence, for one query type
      (single-image VQA), before any other feature work starts

## Next
- [ ] InternVL3-2B running locally, forward pass verified (`trust_remote_code=True`)
- [ ] BigEarthNet.txt / VRSBench / RSVQA / CDVQA download and access verified
- [ ] Domain-gap test: Sentinel-trained baseline against real/representative Cartosat-2S/RISAT
      imagery (Bhoonidhi/Bhuvan) — owned by Aashritha, do not leave unowned
- [ ] Agentic router + verification layer wired end to end for all four mandatory task types
- [ ] Evidence schema rendering correctly in the frontend (bbox/mask overlays, confidence,
      trace panel)

## Later
- [ ] Real benchmark numbers captured (VRSBench/RSVQA/CDVQA + BigEarthNet.txt benchmark split)
      before submission — never estimated or pre-filled
- [ ] Downloadable PDF report generation
- [ ] Demo rehearsed against cached data, including the deliberate trick-question moment,
      with a recorded backup
- [ ] Bonus features (archive search, confounder gate, similar-sites clustering) — only if the
      mandatory scope is fully done and time remains; cut first under pressure, per PRD §11

## Explicitly rejected (do not re-propose)
- Synthetic caption generation from BigEarthNet-MM classification labels — BigEarthNet.txt
  already ships real text annotations.
- A trained pixel-level optical–SAR fusion network — late fusion + rule-based reconciliation
  chosen instead (see ARCHITECTURE.md, "Decisions expensive to reverse").
- LangGraph / free-form ReAct agent loop for the router — the PS specifies a narrow classifier,
  not an open planner.
- Supabase — free-tier auto-pause after 7 days is unacceptable for this project's cadence.
