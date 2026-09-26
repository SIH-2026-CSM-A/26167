"""Record each demo preset's answer from a real live run, for cached demo serving.

Posts every preset in data/demo/manifest.json to a running backend with run_live=true, so VQA
and change detection go through the configured inference Space. Writes
data/demo/cached/<preset_id>.json.gz only when the response is a live run; a cached or failed
response is never written. Nothing in a recording is typed by hand.

    uv run python scripts/record_demo_answers.py --base-url http://localhost:8000 \
        --email you@example.com --password '...'

Re-run after changing model weights or pipeline logic; commit the .json.gz files it writes.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

# Same as scripts/run_benchmarks.py: running a file puts scripts/, not bck/, on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.demo_manifest import DEMO_ROOT, load_demo_manifest  # noqa: E402

CACHED_DIR = DEMO_ROOT / "cached"
_ROLE_ORDER = {"pre_image": 0, "post_image": 1}
_REMOTE_CALL_ACTIONS = {"remote_vqa_call", "remote_change_detect_call"}


def _model_identity(answer: dict) -> dict | None:
    for step in answer["trace"]["steps"]:
        if step["action"] in _REMOTE_CALL_ACTIONS:
            return step["params"].get("model_identity")
    return None  # fusion runs on the backend itself; no remote model involved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()

    manifest = load_demo_manifest()
    CACHED_DIR.mkdir(parents=True, exist_ok=True)
    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        login = client.post("/auth/login", json={"email": args.email, "password": args.password})
        login.raise_for_status()
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        failures = 0
        for preset in manifest.presets:
            assets = sorted(preset.assets, key=lambda asset: _ROLE_ORDER.get(asset.role, 0))
            files = []
            data: dict[str, object] = {"query": preset.query, "run_live": "true"}
            modalities, orders, hashes = [], [], {}
            for index, asset in enumerate(assets):
                content = (DEMO_ROOT / asset.path).read_bytes()
                hashes[asset.id] = hashlib.sha256(content).hexdigest()
                files.append(("images", (Path(asset.path).name, content)))
                modalities.append(asset.modality)
                orders.append(str(index))
            data["modality"] = modalities
            if preset.intent == "change_vqa":
                data["capture_order"] = orders

            response = client.post("/query", data=data, files=files, headers=headers)
            if response.status_code != 200:
                print(f"FAIL {preset.id}: HTTP {response.status_code} {response.text[:300]}")
                failures += 1
                continue
            answer = response.json()
            if answer.get("served_from") != "live":
                print(
                    f"FAIL {preset.id}: response was not a live run ({answer.get('served_from')})"
                )
                failures += 1
                continue
            recording = {
                "recorded_at": datetime.now(UTC).isoformat(),
                "preset_id": preset.id,
                "query": preset.query,
                "asset_sha256": hashes,
                "model_identity": _model_identity(answer),
                "answer": answer,
            }
            # Compact + gzip: answers embed full mask arrays (tens of MB as indented JSON).
            path = CACHED_DIR / f"{preset.id}.json.gz"
            path.write_bytes(
                gzip.compress(json.dumps(recording, separators=(",", ":")).encode(), mtime=0)
            )
            print(f"OK   {preset.id} -> {path}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
