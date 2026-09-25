"""Serve demo presets from recorded real runs.

A recording (data/demo/cached/<preset_id>.json) is the full Answer of a real live run of that
preset, written by scripts/record_demo_answers.py. It's served only when the uploaded files are
byte-identical to the preset's assets (sha256) and the question is the preset's question, so a
recording can never be passed off as the answer for other images or another question.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.contracts import Answer, CachedRunInfo
from app.core.demo_manifest import DEMO_ROOT, DemoManifestError, load_demo_manifest
from app.core.logging import get_logger
from app.inference.identity import EXPECTED_MODEL_IDENTITY, identity_mismatches
from app.inference.remote import last_model_identity

logger = get_logger(__name__)

CACHED_DIR = DEMO_ROOT / "cached"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@lru_cache
def _preset_index(demo_root: Path) -> dict[tuple[str, frozenset[str]], str]:
    """(query, asset hashes) -> preset id, for every preset in the manifest."""
    try:
        manifest = load_demo_manifest(demo_root / "manifest.json")
    except DemoManifestError as error:
        logger.warning("Demo manifest unavailable; cached demo answers disabled: %s", error)
        return {}
    index: dict[tuple[str, frozenset[str]], str] = {}
    for preset in manifest.presets:
        hashes = frozenset(
            sha256_bytes((demo_root / asset.path).read_bytes()) for asset in preset.assets
        )
        index[(preset.query.strip(), hashes)] = preset.id
    return index


def load_recording(preset_id: str, cached_dir: Path) -> dict[str, Any] | None:
    path = cached_dir / f"{preset_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def find_cached_answer(
    *,
    query: str,
    upload_contents: list[bytes],
    reason: str,
    demo_root: Path | None = None,
    cached_dir: Path | None = None,
) -> Answer | None:
    """The recorded Answer for this exact preset input, or None if there is no match."""
    demo_root = demo_root or DEMO_ROOT
    cached_dir = cached_dir or CACHED_DIR
    key = (query.strip(), frozenset(sha256_bytes(content) for content in upload_contents))
    if len(key[1]) != len(upload_contents):
        return None  # duplicate uploads never match a preset
    preset_id = _preset_index(demo_root).get(key)
    if preset_id is None:
        return None
    recording = load_recording(preset_id, cached_dir)
    if recording is None:
        logger.info("Demo preset %s matched but has no recording yet.", preset_id)
        return None

    recorded_identity = recording.get("model_identity")
    mismatched = identity_mismatches(recorded_identity, EXPECTED_MODEL_IDENTITY)
    live_identity = last_model_identity()
    mismatched += [
        f"live:{key}"
        for key in identity_mismatches(recorded_identity, live_identity)
        if key not in mismatched
    ]
    if mismatched:
        logger.warning(
            "Serving recorded demo answer %s whose model identity no longer matches (%s); "
            "re-record with scripts/record_demo_answers.py.",
            preset_id,
            ", ".join(mismatched),
        )

    answer = Answer.model_validate(recording["answer"])
    return answer.model_copy(
        update={
            "served_from": "cached_demo",
            "cached_run": CachedRunInfo(
                recorded_at=datetime.fromisoformat(recording["recorded_at"]),
                preset_id=preset_id,
                reason=reason,
                model_identity=recorded_identity,
                identity_mismatch=bool(mismatched),
            ),
        }
    )
