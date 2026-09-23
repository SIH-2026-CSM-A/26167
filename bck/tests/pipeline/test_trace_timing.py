"""Trace steps record the real start and end of the work they cover."""

import time
from datetime import UTC, datetime

from app.pipeline.stages import TraceRecorder

STAGE_SLEEP_SECONDS = 0.05


def test_stage_step_spans_its_work() -> None:
    recorder = TraceRecorder()
    started = datetime.now(UTC)
    time.sleep(STAGE_SLEEP_SECONDS)
    recorder.record("tools.demo", "demo_completed", started_at=started)

    step = recorder.build().steps[0]
    assert step.started_at == started
    assert (step.completed_at - step.started_at).total_seconds() >= STAGE_SLEEP_SECONDS


def test_event_without_started_at_is_instant() -> None:
    recorder = TraceRecorder()
    recorder.record("pipeline", "request_received")

    step = recorder.build().steps[0]
    assert (step.completed_at - step.started_at).total_seconds() < STAGE_SLEEP_SECONDS


def test_explicit_completed_at_is_kept_for_work_recorded_later() -> None:
    recorder = TraceRecorder()
    started = datetime.now(UTC)
    time.sleep(STAGE_SLEEP_SECONDS)
    finished = datetime.now(UTC)
    time.sleep(STAGE_SLEEP_SECONDS)
    recorder.record("validation", "eo_gates", started_at=started, completed_at=finished)

    step = recorder.build().steps[0]
    assert step.completed_at == finished
