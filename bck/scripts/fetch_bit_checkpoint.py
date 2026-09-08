"""B12: fetch and verify the BIT_CD pretrained LEVIR-CD checkpoint.

Source: BIT's own published Google Drive release asset, linked from the
upstream README (see bit_vendor/VENDORED.md's "Pretrained weights" section)
— https://github.com/justchenhao/BIT_CD, file id 1IVdF5a3e1_7DiSndtMkhpZuCSgDLLFcg.
Never a different mirror: this is the exact file app.pipeline.pipeline's
BIT_CHECKPOINT_PATH and bit_vendor's own model code expect.

Usage: uv run python scripts/fetch_bit_checkpoint.py
"""

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
from pathlib import Path

import requests

FILE_ID = "1IVdF5a3e1_7DiSndtMkhpZuCSgDLLFcg"
DOWNLOAD_URL = f"https://drive.google.com/uc?export=download&id={FILE_ID}"
EXPECTED_SHA256 = "c159ba76143447f58c9f367ce8126a0014f2e4ba218cdb97cca173952c38cb3b"
EXPECTED_SIZE_BYTES = 60_048_699
DEST_PATH = Path(__file__).resolve().parents[1] / "checkpoints" / "BIT_LEVIR" / "best_ckpt.pt"
_CHUNK_SIZE = 1024 * 1024
_REQUEST_TIMEOUT_SECONDS = 60


class ChecksumError(RuntimeError):
    """Raised when a downloaded file's hash or size doesn't match the expected checkpoint."""


def _extract_confirm_token(response: requests.Response) -> str | None:
    """Pull Google Drive's large-file virus-scan-warning confirm token, if present."""
    for key, value in response.cookies.items():
        if key.startswith("download_warning"):
            return value
    match = re.search(r'name="confirm"\s+value="([0-9A-Za-z_-]+)"', response.text)
    if match:
        return match.group(1)
    match = re.search(r"confirm=([0-9A-Za-z_-]+)&", response.text)
    if match:
        return match.group(1)
    return None


def _download(
    session: requests.Session, url: str, params: dict[str, str] | None = None
) -> requests.Response:
    response = session.get(url, params=params, stream=True, timeout=_REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response


def _looks_like_html(response: requests.Response) -> bool:
    content_type = response.headers.get("Content-Type", "")
    return "text/html" in content_type


def fetch_checkpoint() -> Path:
    """Download, verify, and stage the BIT LEVIR-CD checkpoint. Raises on any failure."""
    session = requests.Session()
    response = _download(session, DOWNLOAD_URL)

    if _looks_like_html(response):
        # Large-file virus-scan warning page instead of the file itself.
        token = _extract_confirm_token(response)
        if token is None:
            raise ChecksumError(
                "Google Drive returned an HTML warning page instead of the file, and no "
                "confirm token could be extracted from it. The upstream link or Drive's "
                "warning-page format may have changed — refusing to guess."
            )
        response = _download(session, DOWNLOAD_URL, params={"confirm": token})
        if _looks_like_html(response):
            raise ChecksumError(
                "Google Drive still returned an HTML page after retrying with a confirm "
                "token. Refusing to accept a non-binary response as the checkpoint."
            )

    hasher = hashlib.sha256()
    downloaded_bytes = 0
    DEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=DEST_PATH.parent, delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        try:
            for chunk in response.iter_content(chunk_size=_CHUNK_SIZE):
                if not chunk:
                    continue
                tmp_file.write(chunk)
                hasher.update(chunk)
                downloaded_bytes += len(chunk)
                if downloaded_bytes > EXPECTED_SIZE_BYTES:
                    raise ChecksumError(
                        f"Downloaded {downloaded_bytes} bytes, already past the expected "
                        f"{EXPECTED_SIZE_BYTES} bytes — aborting rather than accepting an "
                        "oversized file."
                    )
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise

        if downloaded_bytes != EXPECTED_SIZE_BYTES:
            tmp_path.unlink(missing_ok=True)
            raise ChecksumError(
                f"Downloaded {downloaded_bytes} bytes; expected exactly "
                f"{EXPECTED_SIZE_BYTES} bytes. Partial or truncated download — refusing "
                "to stage it."
            )

        actual_sha256 = hasher.hexdigest()
        if actual_sha256 != EXPECTED_SHA256:
            tmp_path.unlink(missing_ok=True)
            raise ChecksumError(
                f"SHA-256 mismatch: got {actual_sha256}, expected {EXPECTED_SHA256}. "
                "Refusing to stage an unverified file."
            )

    tmp_path.replace(DEST_PATH)
    return DEST_PATH


def main() -> int:
    try:
        dest = fetch_checkpoint()
    except (ChecksumError, requests.RequestException) as error:
        print(f"fetch_bit_checkpoint failed: {error}", file=sys.stderr)
        return 1
    print(
        f"BIT checkpoint verified and staged at {dest} "
        f"({EXPECTED_SIZE_BYTES} bytes, sha256={EXPECTED_SHA256})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
