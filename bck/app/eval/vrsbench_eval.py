r"""VRSBench evaluation harness for AASH-003's tool-based visual grounding.

Runs `app.tools.vqa_grounding.execute_vqa` (backed by the real `InternVLAdapter`)
over VRSBench's held-out eval splits and scores it. Built to run in a Colab /
Kaggle GPU notebook: `%run vrsbench_eval.py` or `python -m app.eval.vrsbench_eval`.

================================================================================
DELIBERATE EVALUATION ADAPTATIONS  (read before trusting any number this emits)
================================================================================

1. TRIGGER-PHRASE WRAPPING ON THE REFERRING PASS.
   VRSBench referring expressions are bare noun phrases, e.g.
       "The large yellow vehicle situated closest to the green area."
   AASH-003's spatial (bbox) pass only activates when the question text matches
   `SPATIAL_TRIGGER_PATTERN` (== r"\b(highlight|locate|where|point out)\b",
   imported live from the tool, not re-hardcoded here). A bare noun phrase never
   matches, so the tool would return no box for any referring item.

   To exercise the grounding path at all, every referring expression is wrapped
   as:
       "Locate: {expression}"
   before being handed to `execute_vqa`. This is an explicit evaluation-time
   adaptation, NOT hidden preprocessing.

   KNOWN LIMITATION TO DISCLOSE IN THE WRITE-UP: forcing the trigger this way
   means the referring "trigger-fire rate" is ~100% by construction and tells
   you nothing about how often organic user phrasing would fire the pass. It may
   inflate OR deflate localization numbers relative to real usage: the model is
   now always asked for a box (so it can score boxes it would never have been
   asked for), and "Locate: <noun phrase>" is a phrasing InternVL was not
   necessarily tuned on. Treat referring localization here as "grounding quality
   GIVEN the pass fires", not "end-to-end behaviour on VRSBench phrasing".

2. NO `Locate:` WRAPPING ON THE VQA PASS.
   VQA questions are sent verbatim. The VQA claim-grounding pass is unconditional
   inside `execute_vqa` and produces only text observations (no coordinates), so
   wrapping would change nothing there. The VQA "bbox trigger-fire rate" below is
   measured on the UNMODIFIED question text (fraction already containing
   where/locate/highlight/point out) and is reported for information only.

3. VQA LOCALIZATION IoU IS NOT COMPUTED.
   `VRSBench_EVAL_vqa.json` carries no bounding-box ground truth (fields:
   image_id, question, ground_truth[text], dataset, question_id, type), and the
   claim-grounding pass returns no box. For VQA items where the spatial pass
   nonetheless fires (question already contains a trigger word), the returned
   pixel bbox and its source ARE recorded per-item, but with
       "iou": null, "iou_reason": "no VRSBench VQA ground-truth box"
   and the aggregate reports VQA IoU@0.5 as the literal string
       "N/A - VRSBench_EVAL_vqa.json carries no bounding-box ground truth".

4. COORDINATE CONVENTIONS (fixed, do not silently change).
   - AASH-003 returns bbox as pixel [x1, y1, x2, y2] (corners) relative to the
     INPUT image's actual resolution (see `_parse_native_bbox` in the tool:
     `raw / 1000 * width|height`).
   - VRSBench referring ground truth is the string "{<x1><y1><x2><y2>}", four
     integers on a 0-100 normalized scale (verified over all 16,159 items:
     min 0, max 100), [x1, y1, x2, y2] corners.
   - Every comparison loads THAT image's real (width, height) via PIL and
     converts the VRSBench 0-100 box UP into pixel space (x/100*width,
     y/100*height). No fixed resolution is assumed anywhere. IoU is computed in
     pixel space.

5. VQA ACCURACY METRIC.
   Reported BOTH ways, separately: (a) exact-match on the raw strings (after
   .strip()), (b) normalized match (lowercase, strip punctuation, drop the
   articles a/an/the, collapse whitespace). VRSBench's official evaluation is
   more lenient / semantic than either; these string metrics are a floor, not a
   faithful reproduction of the paper's numbers. Disclose that.

6. IoU THRESHOLD is 0.5 for the referring localization-accuracy metric. Fixed.

If AASH-003's interface differs from what this script imports/assumes, the script
raises at import or first use rather than guessing (see `_assert_interface`).
"""

# NOTE: this file deliberately exceeds the repo's 300-line-per-file standard. It
# is an offline benchmark harness (outside the app import graph) meant to be run
# as a single notebook cell / `%run`, so it is kept as one self-contained script
# rather than split across modules. Intentional exception, not an oversight.

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# CONFIG                                                                       #
# --------------------------------------------------------------------------- #

# Location of the repo's `bck/` dir, prepended to sys.path so `import app.*`
# works when this file is run standalone from a notebook. Auto-detected from
# this file's own location (…/bck/app/eval/vrsbench_eval.py -> …/bck); override
# with the env var VRSBENCH_BCK_DIR if you copied the script elsewhere.
REPO_BCK_DIR = Path(os.environ.get("VRSBENCH_BCK_DIR", Path(__file__).resolve().parents[2]))

# VRSBench data, downloaded under data/benchmarks/vrsbench/ (YASH-012 step).
# Override with VRSBENCH_DATA_DIR for Colab/Kaggle paths.
DATA_DIR = Path(
    os.environ.get("VRSBENCH_DATA_DIR", REPO_BCK_DIR.parent / "data" / "benchmarks" / "vrsbench")
)
VQA_JSON = DATA_DIR / "VRSBench_EVAL_vqa.json"
REF_JSON = DATA_DIR / "VRSBench_EVAL_referring.json"
IMAGES_DIR = DATA_DIR / "Images_val"

OUT_DIR = Path(os.environ.get("VRSBENCH_OUT_DIR", DATA_DIR / "eval_out"))

# Documented counts from the ticket / dataset card. The script VERIFIES the real
# counts against these and reports both; it does not trust them.
DOCUMENTED_VQA_COUNT = 37_409
DOCUMENTED_REF_COUNT = 16_159

# None => evaluate the full loaded split (the Colab/Kaggle default). Set to an
# int for a quick smoke test; subsampling is deterministic (stable sort by
# image_id, question_id, then take the first N) so resume still works.
SUBSAMPLE_N: int | None = None

# Flush partial results to disk every this many processed items, so an
# interrupted run resumes instead of restarting.
CHECKPOINT_EVERY = 50

IOU_THRESHOLD = 0.5
REF_WRAP_TEMPLATE = "Locate: {expression}"

# Model: the tool's own default checkpoint. Left explicit so the results file
# records exactly what ran. `device=None` lets InternVLAdapter pick cuda if present.
MODEL_ID = "OpenGVLab/InternVL3-2B"
MODEL_DEVICE: str | None = None

_ARTICLES = {"a", "an", "the"}
_VRSBENCH_BOX_RE = re.compile(r"<(\d+)>")


# --------------------------------------------------------------------------- #
# INTERFACE IMPORT + GUARD                                                     #
# --------------------------------------------------------------------------- #

if str(REPO_BCK_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_BCK_DIR))

try:
    from app.models.internvl import InternVLAdapter
    from app.tools.vqa_grounding import VqaToolError, VqaToolResult, execute_vqa
    from app.tools.vqa_grounding.tool import SPATIAL_TRIGGER_PATTERN
except Exception as exc:  # pragma: no cover - import-time environment problem
    raise RuntimeError(
        "Could not import AASH-003's tool / model interface from "
        f"{REPO_BCK_DIR}. Fix VRSBENCH_BCK_DIR or the environment before "
        f"running the eval. Original error: {exc!r}"
    ) from exc


def _assert_interface() -> None:
    """Fail loudly if AASH-003's surface no longer matches this script's assumptions.

    Per YASH-012: stop and report an interface mismatch, never guess around it.
    """
    import inspect

    sig = inspect.signature(execute_vqa)
    params = list(sig.parameters)
    expected = ["image", "question", "source_asset_id", "model"]
    if params != expected:
        raise RuntimeError(
            f"execute_vqa signature changed: expected keyword params {expected}, "
            f"got {params}. Re-check the eval design before trusting results."
        )
    for name in ("raw_answer", "supporting_observations", "bbox", "bbox_source", "bbox_label"):
        if name not in VqaToolResult.__dataclass_fields__:
            raise RuntimeError(
                f"VqaToolResult no longer has field {name!r}; eval assumptions broken."
            )
    probe = "please locate the runway"
    if SPATIAL_TRIGGER_PATTERN.search(probe) is None:
        raise RuntimeError(
            "SPATIAL_TRIGGER_PATTERN no longer matches 'locate' - the "
            f"'{REF_WRAP_TEMPLATE}' wrapping would no longer fire the bbox pass. "
            "Re-check the referring-pass adaptation before running."
        )
    if not callable(getattr(InternVLAdapter, "generate", None)):
        raise RuntimeError(
            "InternVLAdapter has no generate(); it no longer satisfies the VqaModel "
            "protocol execute_vqa expects."
        )
    # model_id / device are set in __init__; probe an instance (lazy, no weights load).
    probe_adapter = InternVLAdapter(model_id=MODEL_ID, device=MODEL_DEVICE)
    for attr in ("model_id", "device"):
        if not isinstance(getattr(probe_adapter, attr, None), str):
            raise RuntimeError(
                f"InternVLAdapter instance is missing a str {attr!r}; it no longer "
                "satisfies the VqaModel protocol execute_vqa expects."
            )


# --------------------------------------------------------------------------- #
# SCORING PRIMITIVES                                                           #
# --------------------------------------------------------------------------- #


def normalize_answer(text: str) -> str:
    """Lowercase, strip punctuation, drop a/an/the, collapse whitespace."""
    lowered = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [t for t in lowered.split() if t not in _ARTICLES]
    return " ".join(tokens)


def parse_vrsbench_box(ground_truth: str) -> list[int] | None:
    """'{<x1><y1><x2><y2>}' -> [x1, y1, x2, y2] ints on the 0-100 scale.

    Returns None if the string does not hold exactly four integers.
    """
    nums = _VRSBENCH_BOX_RE.findall(ground_truth or "")
    if len(nums) != 4:
        return None
    return [int(n) for n in nums]


def vrsbench_box_to_pixels(box_0_100: list[int], width: int, height: int) -> list[float]:
    """VRSBench normalized 0-100 [x1,y1,x2,y2] -> pixel [x1,y1,x2,y2] for THIS image."""
    x1, y1, x2, y2 = box_0_100
    return [
        x1 / 100.0 * width,
        y1 / 100.0 * height,
        x2 / 100.0 * width,
        y2 / 100.0 * height,
    ]


def iou_xyxy(a: list[float], b: list[float]) -> float:
    """IoU of two [x1,y1,x2,y2] boxes in the same (pixel) space."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = inter_w * inter_h
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


# --------------------------------------------------------------------------- #
# LOADING + RESUME                                                            #
# --------------------------------------------------------------------------- #


def load_split(path: Path, documented: int, label: str) -> list[dict[str, Any]]:
    """Load a VRSBench eval JSON and report the real count vs the documented one."""
    if not path.exists():
        raise FileNotFoundError(f"{label} JSON not found at {path}")
    with path.open(encoding="utf-8") as handle:
        items = json.load(handle)
    if not isinstance(items, list):
        raise RuntimeError(f"{label} JSON top level is {type(items).__name__}, expected list")
    actual = len(items)
    flag = "OK" if actual == documented else "MISMATCH"
    print(f"[load] {label}: {actual} items loaded (documented {documented}) -> {flag}")
    items.sort(key=lambda r: (r["image_id"], r["question_id"]))
    if SUBSAMPLE_N is not None:
        items = items[:SUBSAMPLE_N]
        print(f"[load] {label}: SUBSAMPLE_N={SUBSAMPLE_N} -> evaluating {len(items)} items")
    return items


def item_key(split: str, rec: dict[str, Any]) -> str:
    """Stable per-item id for checkpoint/resume: (image_id, question_id) is unique."""
    return f"{split}:{rec['image_id']}:{rec['question_id']}"


def load_done(jsonl_path: Path) -> dict[str, dict[str, Any]]:
    """Read a partial-results JSONL back into {key: record} for resume."""
    done: dict[str, dict[str, Any]] = {}
    if not jsonl_path.exists():
        return done
    with jsonl_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue  # tolerate a half-written trailing line from a hard kill
            if "key" in rec:
                done[rec["key"]] = rec
    if done:
        print(f"[resume] {jsonl_path.name}: {len(done)} items already done, skipping them")
    return done


class Checkpointer:
    """Append records to a JSONL, flushing to disk every CHECKPOINT_EVERY items."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a", encoding="utf-8")
        self._since_flush = 0

    def add(self, record: dict[str, Any]) -> None:
        self._handle.write(json.dumps(record) + "\n")
        self._since_flush += 1
        if self._since_flush >= CHECKPOINT_EVERY:
            self.flush()

    def flush(self) -> None:
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self._since_flush = 0

    def close(self) -> None:
        self.flush()
        self._handle.close()


# --------------------------------------------------------------------------- #
# IMAGE HELPER                                                                 #
# --------------------------------------------------------------------------- #


def open_rgb(image_id: str) -> tuple[Any, tuple[int, int]]:
    """Open Images_val/<image_id> as RGB PIL image; return (image, (width, height))."""
    from PIL import Image

    path = IMAGES_DIR / image_id
    if not path.exists():
        raise FileNotFoundError(f"image not found: {path}")
    img = Image.open(path).convert("RGB")
    return img, img.size  # PIL .size is (width, height)


# --------------------------------------------------------------------------- #
# PASSES                                                                       #
# --------------------------------------------------------------------------- #


def run_vqa_pass(
    model: InternVLAdapter, items: list[dict[str, Any]], jsonl_path: Path
) -> list[dict[str, Any]]:
    """Answer + claim-grounding for every VQA item. No IoU (no GT boxes)."""
    done = load_done(jsonl_path)
    ck = Checkpointer(jsonl_path)
    results: list[dict[str, Any]] = list(done.values())
    total = len(items)
    try:
        for i, rec in enumerate(items, 1):
            key = item_key("vqa", rec)
            if key in done:
                continue
            question = rec["question"]
            gt_answer = str(rec.get("ground_truth", ""))
            trigger_fired = SPATIAL_TRIGGER_PATTERN.search(question) is not None
            out: dict[str, Any] = {
                "key": key,
                "split": "vqa",
                "image_id": rec["image_id"],
                "question_id": rec["question_id"],
                "type": rec.get("type"),
                "question": question,
                "gt_answer": gt_answer,
                "pred_answer": None,
                "exact_match": None,
                "normalized_match": None,
                "trigger_fired": trigger_fired,
                "bbox_pred_px": None,
                "bbox_source": None,
                "bbox_label": None,
                "image_size": None,
                "iou": None,
                "iou_reason": "no VRSBench VQA ground-truth box",
                "timing_seconds": None,
                "error": None,
            }
            try:
                image, size = open_rgb(rec["image_id"])
                out["image_size"] = list(size)
                started = time.perf_counter()
                res: VqaToolResult = execute_vqa(
                    image=image,
                    question=question,
                    source_asset_id=rec["image_id"],
                    model=model,
                )
                out["timing_seconds"] = round(time.perf_counter() - started, 3)
                out["pred_answer"] = res.raw_answer
                out["exact_match"] = res.raw_answer.strip() == gt_answer.strip()
                out["normalized_match"] = normalize_answer(res.raw_answer) == normalize_answer(
                    gt_answer
                )
                out["bbox_pred_px"] = res.bbox
                out["bbox_source"] = res.bbox_source
                out["bbox_label"] = res.bbox_label
            except (VqaToolError, ValueError, FileNotFoundError) as err:
                out["error"] = f"{type(err).__name__}: {err}"
            except Exception as err:  # keep the run alive; record and move on
                out["error"] = f"{type(err).__name__}: {err}"
                traceback.print_exc()
            ck.add(out)
            results.append(out)
            if i % CHECKPOINT_EVERY == 0 or i == total:
                print(f"[vqa] {i}/{total} processed")
    finally:
        ck.close()
    return results


def run_referring_pass(
    model: InternVLAdapter, items: list[dict[str, Any]], jsonl_path: Path
) -> list[dict[str, Any]]:
    """'Locate: {expr}' -> bbox pass -> IoU@0.5 vs VRSBench GT box in pixel space."""
    done = load_done(jsonl_path)
    ck = Checkpointer(jsonl_path)
    results: list[dict[str, Any]] = list(done.values())
    total = len(items)
    try:
        for i, rec in enumerate(items, 1):
            key = item_key("ref", rec)
            if key in done:
                continue
            expression = rec["question"]
            wrapped = REF_WRAP_TEMPLATE.format(expression=expression)
            gt_box_0_100 = parse_vrsbench_box(rec.get("ground_truth", ""))
            out: dict[str, Any] = {
                "key": key,
                "split": "referring",
                "image_id": rec["image_id"],
                "question_id": rec["question_id"],
                "expression": expression,
                "wrapped_question": wrapped,
                "gt_box_0_100": gt_box_0_100,
                "gt_box_px": None,
                "image_size": None,
                "trigger_fired": SPATIAL_TRIGGER_PATTERN.search(wrapped) is not None,
                "pred_answer": None,
                "bbox_pred_px": None,
                "bbox_source": None,
                "iou": None,
                "iou_at_0.5": None,
                "timing_seconds": None,
                "error": None,
            }
            try:
                if gt_box_0_100 is None:
                    raise ValueError(f"unparseable VRSBench GT box: {rec.get('ground_truth')!r}")
                image, size = open_rgb(rec["image_id"])
                out["image_size"] = list(size)
                gt_px = vrsbench_box_to_pixels(gt_box_0_100, size[0], size[1])
                out["gt_box_px"] = [round(v, 2) for v in gt_px]
                started = time.perf_counter()
                res = execute_vqa(
                    image=image,
                    question=wrapped,
                    source_asset_id=rec["image_id"],
                    model=model,
                )
                out["timing_seconds"] = round(time.perf_counter() - started, 3)
                out["pred_answer"] = res.raw_answer
                out["bbox_pred_px"] = res.bbox
                out["bbox_source"] = res.bbox_source
                if res.bbox is not None:
                    score = iou_xyxy([float(v) for v in res.bbox], gt_px)
                    out["iou"] = round(score, 4)
                    out["iou_at_0.5"] = score >= IOU_THRESHOLD
                else:
                    out["iou"] = 0.0
                    out["iou_at_0.5"] = False
            except (VqaToolError, ValueError, FileNotFoundError) as err:
                out["error"] = f"{type(err).__name__}: {err}"
            except Exception as err:
                out["error"] = f"{type(err).__name__}: {err}"
                traceback.print_exc()
            ck.add(out)
            results.append(out)
            if i % CHECKPOINT_EVERY == 0 or i == total:
                print(f"[ref] {i}/{total} processed")
    finally:
        ck.close()
    return results


# --------------------------------------------------------------------------- #
# AGGREGATION                                                                  #
# --------------------------------------------------------------------------- #


def _rate(numer: int, denom: int) -> float | None:
    return round(numer / denom, 4) if denom else None


def _source_breakdown(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {"internvl_native": 0, "otsu_fallback": 0, "none": 0}
    for r in records:
        counts[r.get("bbox_source") or "none"] += 1
    return counts


def aggregate_vqa(records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in records if r["error"] is None and r["pred_answer"] is not None]
    errors = [r for r in records if r["error"] is not None]
    exact = sum(1 for r in scored if r["exact_match"])
    norm = sum(1 for r in scored if r["normalized_match"])
    triggered = [r for r in scored if r["trigger_fired"]]
    triggered_with_box = [r for r in triggered if r["bbox_pred_px"] is not None]
    return {
        "items_evaluated": len(records),
        "items_scored": len(scored),
        "items_errored": len(errors),
        "accuracy_exact_match": _rate(exact, len(scored)),
        "accuracy_normalized_match": _rate(norm, len(scored)),
        "accuracy_metric_note": (
            "exact = raw string equality after strip(); normalized = lowercase, "
            "punctuation stripped, articles a/an/the removed, whitespace collapsed. "
            "VRSBench's official metric is more lenient/semantic; treat these as a floor."
        ),
        "bbox_trigger_fire_rate": _rate(len(triggered), len(scored)),
        "bbox_trigger_fire_note": (
            "fraction of UNMODIFIED VQA questions matching "
            "highlight|locate|where|point out; informational only"
        ),
        "bbox_pass_returned_box_count": len(triggered_with_box),
        "bbox_source_breakdown": _source_breakdown(scored),
        "iou_at_0.5": "N/A - VRSBench_EVAL_vqa.json carries no bounding-box ground truth",
    }


def aggregate_referring(records: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in records if r["error"] is None and r["iou"] is not None]
    errors = [r for r in records if r["error"] is not None]
    triggered = [r for r in scored if r["trigger_fired"]]
    with_box = [r for r in scored if r["bbox_pred_px"] is not None]
    hits = sum(1 for r in scored if r["iou_at_0.5"])
    hits_of_returned = sum(1 for r in with_box if r["iou_at_0.5"])
    mean_iou_all = round(sum(r["iou"] for r in scored) / len(scored), 4) if scored else None
    mean_iou_returned = (
        round(sum(r["iou"] for r in with_box) / len(with_box), 4) if with_box else None
    )
    return {
        "items_evaluated": len(records),
        "items_scored": len(scored),
        "items_errored": len(errors),
        "trigger_fire_rate": _rate(len(triggered), len(scored)),
        "trigger_fire_note": (
            f"~1.0 by construction - every expression wrapped as '{REF_WRAP_TEMPLATE}'"
        ),
        "returned_box_count": len(with_box),
        "returned_box_rate": _rate(len(with_box), len(scored)),
        "bbox_source_breakdown": _source_breakdown(scored),
        "mean_iou_all": mean_iou_all,
        "mean_iou_over_returned": mean_iou_returned,
        "localization_acc_iou_0.5": _rate(hits, len(scored)),
        "localization_acc_iou_0.5_note": (
            "denominator = all scored items; no box returned counts as a miss"
        ),
        "localization_acc_iou_0.5_over_returned": _rate(hits_of_returned, len(with_box)),
        "iou_threshold": IOU_THRESHOLD,
    }


# --------------------------------------------------------------------------- #
# DRIVER                                                                       #
# --------------------------------------------------------------------------- #


@dataclass
class Paths:
    out_dir: Path
    vqa_jsonl: Path = field(init=False)
    ref_jsonl: Path = field(init=False)
    results_json: Path = field(init=False)

    def __post_init__(self) -> None:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.vqa_jsonl = self.out_dir / "vqa_partial.jsonl"
        self.ref_jsonl = self.out_dir / "referring_partial.jsonl"
        self.results_json = self.out_dir / "vrsbench_eval_results.json"


def main() -> dict[str, Any]:
    _assert_interface()
    paths = Paths(OUT_DIR)

    print(f"[cfg] repo bck dir : {REPO_BCK_DIR}")
    print(f"[cfg] data dir     : {DATA_DIR}")
    print(f"[cfg] out dir      : {paths.out_dir}")
    print(f"[cfg] SUBSAMPLE_N  : {SUBSAMPLE_N}")
    print(f"[cfg] checkpoint   : every {CHECKPOINT_EVERY} items")
    print(f"[cfg] IoU threshold: {IOU_THRESHOLD}")
    print(f"[cfg] ref wrapping : {REF_WRAP_TEMPLATE!r}")
    print(f"[cfg] model        : {MODEL_ID} (device={MODEL_DEVICE or 'auto'})")

    vqa_items = load_split(VQA_JSON, DOCUMENTED_VQA_COUNT, "VQA")
    ref_items = load_split(REF_JSON, DOCUMENTED_REF_COUNT, "referring")

    if not IMAGES_DIR.is_dir():
        raise FileNotFoundError(f"image dir not found: {IMAGES_DIR}")
    n_images = sum(1 for _ in IMAGES_DIR.iterdir())
    print(f"[load] image dir   : {IMAGES_DIR} ({n_images} entries)")

    model = InternVLAdapter(model_id=MODEL_ID, device=MODEL_DEVICE)
    print(f"[model] adapter ready (lazy load on first generate): {model.model_id} @ {model.device}")

    print("\n=== VQA PASS ===")
    vqa_records = run_vqa_pass(model, vqa_items, paths.vqa_jsonl)
    print("\n=== REFERRING PASS ===")
    ref_records = run_referring_pass(model, ref_items, paths.ref_jsonl)

    vqa_records.sort(key=lambda r: r["key"])
    ref_records.sort(key=lambda r: r["key"])

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {
            "model_id": MODEL_ID,
            "model_device_requested": MODEL_DEVICE,
            "subsample_n": SUBSAMPLE_N,
            "checkpoint_every": CHECKPOINT_EVERY,
            "iou_threshold": IOU_THRESHOLD,
            "referring_wrap_template": REF_WRAP_TEMPLATE,
            "spatial_trigger_pattern": SPATIAL_TRIGGER_PATTERN.pattern,
            "data_dir": str(DATA_DIR),
        },
        "counts": {
            "vqa_documented": DOCUMENTED_VQA_COUNT,
            "vqa_loaded_from_file": _loaded_count(VQA_JSON),
            "vqa_evaluated": len(vqa_records),
            "referring_documented": DOCUMENTED_REF_COUNT,
            "referring_loaded_from_file": _loaded_count(REF_JSON),
            "referring_evaluated": len(ref_records),
        },
        "vqa": aggregate_vqa(vqa_records),
        "referring": aggregate_referring(ref_records),
        "adaptations_disclosed": [
            "Referring expressions wrapped as 'Locate: {expr}' to fire AASH-003's "
            "trigger-gated bbox pass; inflates referring trigger-fire rate to ~1.0 "
            "and does not reflect organic VRSBench phrasing.",
            "VQA IoU@0.5 not computed: VRSBench_EVAL_vqa.json has no GT boxes and the "
            "claim-grounding pass returns no coordinates.",
            "VQA accuracy is string-based (exact + normalized), a floor relative to "
            "VRSBench's official semantic metric.",
        ],
    }

    payload = {
        "summary": summary,
        "vqa_items": vqa_records,
        "referring_items": ref_records,
    }
    with paths.results_json.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    print(f"\n[out] wrote {paths.results_json}")

    _print_report(summary)
    return summary


def _loaded_count(path: Path) -> int:
    with path.open(encoding="utf-8") as handle:
        return len(json.load(handle))


def _print_report(summary: dict[str, Any]) -> None:
    c = summary["counts"]
    v = summary["vqa"]
    r = summary["referring"]

    def pct(x: float | None) -> str:
        return "n/a" if x is None else f"{x * 100:.1f}%"

    print("\n" + "=" * 66)
    print("VRSBench x AASH-003 - headline numbers")
    print("=" * 66)
    print(
        f"VQA        loaded={c['vqa_loaded_from_file']} "
        f"(documented {c['vqa_documented']})  evaluated={c['vqa_evaluated']}  "
        f"errored={v['items_errored']}"
    )
    print(f"  exact-match accuracy       : {pct(v['accuracy_exact_match'])}")
    print(f"  normalized-match accuracy  : {pct(v['accuracy_normalized_match'])}")
    print(
        f"  bbox trigger-fire rate     : {pct(v['bbox_trigger_fire_rate'])}  "
        f"(unmodified question text; {v['bbox_pass_returned_box_count']} returned a box)"
    )
    print(f"  IoU@0.5                    : {v['iou_at_0.5']}")
    print(
        f"referring  loaded={c['referring_loaded_from_file']} "
        f"(documented {c['referring_documented']})  evaluated={c['referring_evaluated']}  "
        f"errored={r['items_errored']}"
    )
    print(
        f"  trigger-fire rate          : {pct(r['trigger_fire_rate'])}  "
        f"(after '{REF_WRAP_TEMPLATE}' wrapping - ~100% by construction)"
    )
    print(
        f"  box returned               : {pct(r['returned_box_rate'])}  "
        f"({r['returned_box_count']}/{r['items_scored']})"
    )
    print(f"  mean IoU (all scored)      : {r['mean_iou_all']}")
    print(f"  mean IoU (box returned)    : {r['mean_iou_over_returned']}")
    print(
        f"  localization acc @IoU>=0.5 : {pct(r['localization_acc_iou_0.5'])}  (missing box = miss)"
    )
    print(f"  localization acc (of returned): {pct(r['localization_acc_iou_0.5_over_returned'])}")
    print("=" * 66)
    print("Adaptations in effect (disclose in write-up):")
    for line in summary["adaptations_disclosed"]:
        print(f"  - {line}")
    print("=" * 66)


if __name__ == "__main__":
    main()
