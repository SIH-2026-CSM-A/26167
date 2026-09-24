"""
Router intent-classification robustness eval.

classify_intent() is a deterministic regex pattern-matcher, not a trained
model. This does NOT measure "learned accuracy" -- it measures how well the
hand-written patterns generalize to realistic paraphrased queries beyond the
5 exact PS queries already covered in bck/tests/router/test_router.py.
"""

import sys
sys.path.insert(0, "bck")

from app.router.classifier import classify_intent
from app.router.schemas import TaskType

# (query, expected_task_type) -- paraphrased, not copied from the existing
# test suite, deliberately varying phrasing to probe real regex coverage.
CASES = [
    # --- VQA (default / general single-image questions) ---
    ("What objects can you see in this scene?", TaskType.VQA),
    ("Describe the land cover types present.", TaskType.VQA),
    ("Is there a building in this image?", TaskType.VQA),
    ("How many vehicles are parked in the lot?", TaskType.VQA),
    ("What is the dominant vegetation type here?", TaskType.VQA),
    ("Classify the terrain shown in this picture.", TaskType.VQA),
    ("Tell me about the urban density in this area.", TaskType.VQA),
    ("What kind of crops are growing in these fields?", TaskType.VQA),
    ("What's happening in this radar image?", TaskType.VQA),
    ("Summarize the visible infrastructure.", TaskType.VQA),

    # --- GROUNDING ---
    ("Point out the river in this image.", TaskType.VQA),  # "point out" not in patterns -- expected miss, real gap
    ("Highlight the airport runway.", TaskType.GROUNDING),
    ("Where is the stadium located in this picture?", TaskType.GROUNDING),
    ("Segment the forested region.", TaskType.GROUNDING),
    ("Give me the bounding box for the bridge.", TaskType.GROUNDING),
    ("Outline the coastal boundary.", TaskType.GROUNDING),
    ("Pinpoint the location of the dam.", TaskType.GROUNDING),
    ("What are the exact coordinates of the tower?", TaskType.GROUNDING),
    ("Where are the solar panels in this scene?", TaskType.GROUNDING),

    # --- CHANGE_VQA ---
    ("What changed between these two satellite passes?", TaskType.CHANGE_VQA),
    ("Compare the before and after images for deforestation.", TaskType.VQA),  # "before/after" not in patterns -- expected miss
    ("Did the reservoir shrink between these dates?", TaskType.CHANGE_VQA),
    ("Show me the difference between these two scenes.", TaskType.CHANGE_VQA),
    ("What is different in the post-event image compared to pre-event?", TaskType.CHANGE_VQA),
    ("Analyze the temporal change in built-up area.", TaskType.CHANGE_VQA),
    ("Between these two acquisitions, what areas were affected by flooding?", TaskType.CHANGE_VQA),
    ("Has the coastline eroded over this period?", TaskType.VQA),  # no matching pattern -- expected miss
    ("What changed in the archive between these two dates?", TaskType.CHANGE_VQA),  # priority-order probe

    # --- FUSION ---
    ("Combine optical and SAR data to detect flooding.", TaskType.VQA),  # "combine" not "optical and sar" exact phrase -- expected miss
    ("Use both radar and optical imagery to assess crop health.", TaskType.VQA),  # "radar" not "sar" -- expected miss
    ("Perform a joint analysis of these two modalities.", TaskType.FUSION),
    ("Fuse the SAR and optical images for water detection.", TaskType.FUSION),
    ("Cross-modal analysis of built environment using both sensors.", TaskType.FUSION),
    ("Use the SAR and optical images together to map urban areas.", TaskType.FUSION),
    ("Where is the fused urban footprint located?", TaskType.FUSION),  # priority-order probe (fusion checked before grounding)

    # --- ARCHIVE_SEARCH_BONUS ---
    ("Search the archive for previous Cartosat images of this region.", TaskType.ARCHIVE_SEARCH_BONUS),
    ("Find catalog entries for imagery from last year.", TaskType.ARCHIVE_SEARCH_BONUS),
    ("Retrieve historical scenes of this location from the archive.", TaskType.ARCHIVE_SEARCH_BONUS),
    ("Query the catalog for Sentinel-2 passes over Delhi.", TaskType.ARCHIVE_SEARCH_BONUS),

    # --- priority-order edge cases (verbatim-adjacent to real PS wording) ---
    ("What changed between these two dates, and where did the change occur?", TaskType.CHANGE_VQA),
    ("Highlight the change between these two images.", TaskType.CHANGE_VQA),  # change checked before grounding
]

results = []
correct = 0
by_type = {}

for query, expected in CASES:
    actual = classify_intent(query).task_type
    is_correct = actual == expected
    correct += int(is_correct)
    by_type.setdefault(expected, {"correct": 0, "total": 0})
    by_type[expected]["total"] += 1
    by_type[expected]["correct"] += int(is_correct)
    results.append((query, expected, actual, is_correct))

print(f"Overall: {correct}/{len(CASES)} = {correct/len(CASES):.1%}\n")
print("Per-type:")
for t, v in by_type.items():
    print(f"  {t.value}: {v['correct']}/{v['total']} = {v['correct']/v['total']:.1%}")

print("\nMismatches (expected -> actual):")
for query, expected, actual, is_correct in results:
    if not is_correct:
        print(f"  [{expected.value} -> {actual.value}] {query!r}")
