"""Demo presets served from recorded runs: default, fallback, exact-match only, staleness.

Runs against the real demo manifest and assets under data/demo. The recording itself is a
test fixture written to a temp dir (never the committed recordings), so these tests don't
depend on whether real recordings exist yet.
"""

import gzip
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import Answer, ExecutionTrace, Modality
from app.core.config import get_settings
from app.core.demo_manifest import DEMO_ROOT
from app.db.models import Base
from app.inference import remote
from app.inference.identity import EXPECTED_MODEL_IDENTITY
from app.pipeline import PipelineError, PipelineUpload, cached_demo, run

PRESET_ID = "bi-temporal-change-location"
QUERY = "What changed between these two dates, and where did the change occur?"
BEFORE = DEMO_ROOT / "assets" / "levir_cd_train_103_9_before.png"
AFTER = DEMO_ROOT / "assets" / "levir_cd_train_103_9_after.png"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path) -> Iterator[None]:
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setenv("INFERENCE_SPACE", "")
    monkeypatch.setattr(cached_demo, "CACHED_DIR", tmp_path)
    monkeypatch.setattr(remote, "_last_model_identity", None)
    get_settings.cache_clear()
    with patch("app.db.session.get_sync_session_maker", return_value=session_maker):
        yield
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)


def _write_recording(tmp_dir, identity=None) -> None:
    answer = Answer(
        text="Recorded answer text (test fixture).",
        trace=ExecutionTrace(trace_id="recorded-trace", created_at=datetime.now(UTC)),
        confidence=0.8,
    )
    recording = {
        "recorded_at": "2026-09-25T10:00:00+00:00",
        "preset_id": PRESET_ID,
        "query": QUERY,
        "asset_sha256": {},
        "model_identity": identity if identity is not None else dict(EXPECTED_MODEL_IDENTITY),
        "answer": answer.model_dump(mode="json"),
    }
    (tmp_dir / f"{PRESET_ID}.json.gz").write_bytes(gzip.compress(json.dumps(recording).encode()))


def _uploads(after_bytes: bytes | None = None) -> list[PipelineUpload]:
    return [
        PipelineUpload(
            id="pre",
            filename=BEFORE.name,
            content_type="image/png",
            content=BEFORE.read_bytes(),
            modality=Modality.OPTICAL,
            capture_order=0,
        ),
        PipelineUpload(
            id="post",
            filename=AFTER.name,
            content_type="image/png",
            content=after_bytes if after_bytes is not None else AFTER.read_bytes(),
            modality=Modality.OPTICAL,
            capture_order=1,
        ),
    ]


def test_demo_preset_is_served_from_its_recording_without_calling_the_space(tmp_path):
    _write_recording(tmp_path)
    with patch.object(remote, "change_detect", side_effect=AssertionError("no live call")):
        answer = run(query=QUERY, uploads=_uploads(), prefer_cached=True)
    assert answer.served_from == "cached_demo"
    assert answer.text == "Recorded answer text (test fixture)."
    assert answer.cached_run is not None
    assert answer.cached_run.reason == "demo_default"
    assert answer.cached_run.preset_id == PRESET_ID
    assert answer.cached_run.recorded_at == datetime(2026, 9, 25, 10, tzinfo=UTC)
    assert answer.cached_run.identity_mismatch is False


def test_live_run_with_inference_unavailable_falls_back_to_the_recording(tmp_path):
    _write_recording(tmp_path)
    answer = run(query=QUERY, uploads=_uploads())
    assert answer.served_from == "cached_demo"
    assert answer.cached_run is not None
    assert answer.cached_run.reason == "INFERENCE_UNAVAILABLE"


def test_quota_error_falls_back_with_the_quota_reason(tmp_path):
    _write_recording(tmp_path)
    with patch.object(remote, "change_detect", side_effect=remote.QuotaExceeded("quota")):
        answer = run(query=QUERY, uploads=_uploads())
    assert answer.cached_run is not None
    assert answer.cached_run.reason == "INFERENCE_QUOTA"


def test_changed_image_bytes_never_match_a_recording(tmp_path):
    _write_recording(tmp_path)
    altered = AFTER.read_bytes() + b"\x00"  # still a valid PNG; different sha256
    with pytest.raises(PipelineError) as excinfo:
        run(query=QUERY, uploads=_uploads(altered), prefer_cached=True)
    assert excinfo.value.reason_code == "INFERENCE_UNAVAILABLE"
    assert excinfo.value.status_code == 503


def test_edited_question_never_matches_a_recording(tmp_path):
    _write_recording(tmp_path)
    with pytest.raises(PipelineError) as excinfo:
        run(query=QUERY + " Be brief.", uploads=_uploads(), prefer_cached=True)
    assert excinfo.value.reason_code == "INFERENCE_UNAVAILABLE"


def test_matching_preset_without_a_recording_reports_the_inference_error():
    with pytest.raises(PipelineError) as excinfo:
        run(query=QUERY, uploads=_uploads(), prefer_cached=True)
    assert excinfo.value.reason_code == "INFERENCE_UNAVAILABLE"


def test_stale_recording_is_served_but_flagged_and_logged(tmp_path, caplog):
    _write_recording(tmp_path, identity=dict(EXPECTED_MODEL_IDENTITY, bit_sha256="0" * 64))
    with caplog.at_level(logging.WARNING):
        answer = run(query=QUERY, uploads=_uploads(), prefer_cached=True)
    assert answer.cached_run is not None
    assert answer.cached_run.identity_mismatch is True
    assert "bit_sha256" in caplog.text


def test_recording_differing_from_the_last_live_identity_is_flagged(tmp_path, monkeypatch):
    _write_recording(tmp_path)
    live = dict(EXPECTED_MODEL_IDENTITY, adapter_sha256="f" * 64)
    monkeypatch.setattr(remote, "_last_model_identity", live)
    answer = run(query=QUERY, uploads=_uploads(), prefer_cached=True)
    assert answer.cached_run is not None
    assert answer.cached_run.identity_mismatch is True
