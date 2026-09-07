"""Write RSVQA-LR benchmark results to a stable, F23-report-citable JSON file."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.evaluation.schemas import ScoreResult

RSVQA_LR_SOURCE = "https://zenodo.org/records/6344334"

# Plain-language note for F23's report generator and any human reading the JSON
# directly: RSVQA-LR is aerial RGB photography at roughly 0.1m ground sample
# distance (per the RSVQA paper, https://arxiv.org/pdf/2003.07333). The evaluated
# adapter (mlp1.1/mlp1.3 LoRA) was trained on Sentinel-2 EuroSAT imagery at 10m GSD
# -- a different sensor and roughly 100x coarser resolution. A low score here
# reflects that domain gap, not a broken evaluation pipeline.
DOMAIN_MISMATCH_NOTE = (
    "RSVQA-LR images are aerial RGB photography at roughly 0.1m ground sample "
    "distance. The evaluated LoRA adapter (mlp1.1/mlp1.3) was trained on Sentinel-2 "
    "EuroSAT imagery at 10m ground sample distance -- a different sensor and "
    "roughly 100x coarser resolution. This accuracy score reflects that domain "
    "gap, not a broken evaluation pipeline."
)

SCOPE_NOTE = (
    "This result covers AC2 (RSVQA-LR) only. AC1 (BigEarthNet.txt manually-verified "
    "benchmark split) is out of scope for YASH-007 and owned by ROHAN-008."
)


def write_results(
    *,
    output_path: Path,
    slice_size: int,
    is_full_active_slice: bool,
    active_image_count: int,
    active_question_count: int,
    subset_seed: int,
    score: ScoreResult,
    model_id: str,
    adapter_path: str,
    adapter_commit: str | None,
) -> None:
    """Write the benchmark result JSON, creating the parent directory if needed.

    `slice_size` must equal the number of predictions actually scored -- never a
    rounded or assumed count. `is_full_active_slice` states plainly whether this run
    used the complete 10,004-question AC2 slice or a smaller diagnostic subset.
    """
    if slice_size != score.num_total:
        raise ValueError(
            f"slice_size ({slice_size}) must equal the number of scored predictions "
            f"({score.num_total}) -- do not report a slice size that wasn't actually run"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "benchmark": "RSVQA-LR",
        "source": RSVQA_LR_SOURCE,
        "model_id": model_id,
        "adapter_path": adapter_path,
        "adapter_commit": adapter_commit,
        "slice_size": slice_size,
        "is_full_active_slice": is_full_active_slice,
        "active_image_count": active_image_count,
        "active_question_count": active_question_count,
        "subset_seed": subset_seed,
        "accuracy": score.overall_accuracy,
        "num_correct": score.num_correct,
        "num_total": score.num_total,
        "accuracy_by_type": score.accuracy_by_type,
        "count_by_type": score.count_by_type,
        "timestamp": datetime.now(UTC).isoformat(),
        "domain_mismatch_note": DOMAIN_MISMATCH_NOTE,
        "scope_note": SCOPE_NOTE,
    }
    output_path.write_text(json.dumps(payload, indent=2))
