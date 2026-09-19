# Demo Dry-Run Log — Post-merge final verification

All 5 manifest presets (`data/demo/manifest.json`) run against the live local stack
(docker compose postgres+titiler, backend uvicorn, frontend npm dev), each confirmed
against the exact manifest query text typed verbatim into the UI.

## 1. single-image-land-cover
- **Query:** "Describe the land-cover and major objects visible in this image."
- **Asset:** sen1floods11_bolivia_103757_s2_optical.tif (single optical slot)
- **Confidence:** 100%
- **Answer:** Thematic/frequency-map-style description — dark region read as minimal/no
  vegetation (possibly water or bare land), lighter complex region as varying land-cover
  intensities (water, vegetation, possibly ice).
- **Evidence:** [06614e1f-0883-4503-be86-d274c5b10859], tool internvl_vqa, type text.

## 2. flood-water-grounding
- **Query:** "Highlight the water body referred to in the query."
- **Asset:** sen1floods11_bolivia_103757_s2_optical.tif (same asset as #1)
- **Confidence:** 81%
- **Answer:** Model hedges — states the water body is not distinctly highlighted in the
  image; describes dark/light shade patterns without committing to a boundary.
- **Evidence:** [ca635a35-836d-4d21-a25e-2d2f8955a9c5] (88%),
  [9d93cbae-8143-4b3d-809e-60b1dfc8c39a] (75%), tool internvl_vqa, type bbox,
  bounds [-65.2321, -14.2475, -65.2192, -14.2334].
- **Note:** Low-confidence, hedged answer on the same imagery that #1 answers well. Worth
  reviewing before demo — the flood-grounding task may want a stronger example asset where
  a water body is unambiguously present.

## 3. cross-modal-built-up-water
- **Query:** "Use the optical and SAR images together to identify built-up and
  water-covered regions."
- **Assets:** optical + SAR pair.
- **Confidence:** 88%
- **Status:** Confirmed clean, run twice identically (pre-existing from prior session).

## 4. bi-temporal-built-up-direction
- **Query:** "Has the built-up area increased, decreased, or remained unchanged?"
- **Assets:** levir_cd_train_103_9_before.png (Slot 1 / pre),
  levir_cd_train_103_9_after.png (Slot 2 / post) — correct temporal order.
- **Confidence:** 95%
- **Answer:** "Change detected (increased) across 41.3% of the scene, located centre."
- **Evidence:** mask, tool change_detection.bit, checkpoint checkpoints/BIT_LEVIR/best_ckpt.pt,
  confounder_suppressed: false, changed_percentage: 41.32843017578125.

## 5. bi-temporal-change-location
- **Query:** "What changed between these two dates, and where did the change occur?"
- **Assets:** same LEVIR pair as #4, same Slot 1 = before / Slot 2 = after order.
- **Confidence:** 95%
- **Answer:** "Change detected (increased) across 41.3% of the scene, located centre."
- **Evidence:** mask, tool change_detection.bit, same checkpoint, confounder_suppressed: false,
  changed_percentage: 41.32843017578125.
- **Note:** Identical numeric output to #4 by design — change_detection.bit is a deterministic
  pixel-diff model and does not vary by query phrasing; the router dispatches the same tool for
  both bi-temporal queries. This is expected, not a copy-paste error.

## Bug found during this dry-run — now FIXED and merged
During bi-temporal testing, feeding the LEVIR pair with pre/post reversed (after.png as pre,
before.png as post) silently flipped confounder_suppressed to true and collapsed
changed_percentage to 0, producing a confident false-negative "No change detected." at 96%.
No error, no warning. Reproduced via the Chat entry point, which appended files in OS
file-picker order rather than temporal order.

Root cause: app/router/planner.py bound pre/post by arrival order, not temporal order, on the
false assumption that request order always equals temporal order (true for Upload's named
slots, false for Chat).

Fix (merged to main): explicit per-image capture_order (0=before, 1=after) carried from the
Upload slots through to the planner, which now binds pre/post from it. A bi-temporal request
without a valid capture_order on both images vetoes (TEMPORAL_ORDER_MISSING) with a clear
message instead of guessing. Consequence: Chat can no longer perform bi-temporal change
detection — it has no way to express temporal order.

## Demo runbook constraint (carried from the fix above)
**Bi-temporal change detection must be run through the Upload page's slots (Slot 1 = before,
Slot 2 = after), never through Chat.** A bi-temporal pair dropped in Chat now returns a veto
message by design. Any live demo of change detection uses Upload.
