"""B7: live deterministic abstention case, F15 acceptance verified end-to-end.

Step 1 finding: the abstention mechanism (SHIVA-004's verify(), 6 acceptance
criteria, tests/verification/test_adversarial_abstention.py) already existed
and was extensively unit-tested — but never actually run end-to-end through
the real pipeline with a genuinely unanswerable query. Its AC1A/AC1C cases
call verify() directly with hand-constructed evidence lists (a real image
path is referenced but never opened by a real tool); its AC6 case runs the
real pipeline but with a confident, non-abstaining fake answer. Neither is
what this ticket asks for. This file is that missing live case, plus the
regression test locking it in — no changes to verify()/rules.py were needed
or made.

Manually verified live (real InternVL3-2B + YASH-004 LoRA adapter, real GPU
inference, this exact fixture and query): the model actually produced a
fully confident, fabricated NDVI walkthrough ("NDVI = (NIR - RED) / (NIR +
RED)... Dark Areas: Areas with high ND[VI]...") for a SAR-only input — a
real hallucination this system needed to catch. It was fully discarded:
answer.text == "", answer.evidence == [], answer.confidence == 0.0,
answer.abstention_reason == "SENSOR_PHYSICAL_LIMITATION: SAR sensors record
microwave backscatter (roughness/dielectric properties), not optical
spectral reflectance or visual color.", and RULE-VERIFY-03 appeared in the
verification_completed trace step's disagreements. Total live wall time was
~107s for that one call.

This regression test reproduces the exact same real fixture, real
ingestion, real router, real verify() call, and real trace — the only
thing swapped is the expensive text-generation step, via
DeterministicVqaModel (the same fast test double every other pipeline test
in this suite already uses, e.g. tests/pipeline/test_pipeline.py). That
swap is provably safe here: RULE-VERIFY-03 (evaluate_sensor_compatibility)
fires from (all-images-SAR, optical-spectral-keyword-in-query) alone,
before it ever looks at evidence content — confirmed directly by the live
run above, where a fully hallucinated, plausible-sounding answer still got
discarded outright. Re-running the real ~107s GPU call on every `pytest -q`
invocation would add that cost to every future gate for zero additional
coverage.
"""

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import Modality
from app.db.models import Base
from app.pipeline import PipelineUpload, run
from tests.helpers import DeterministicVqaModel

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
S1_PATH = FIXTURES_DIR / "Bolivia_103757_S1Hand.tif"

QUERY = "Calculate NDVI and check the visual green color of vegetation in this image."


@pytest.fixture(autouse=True)
def sqlite_db() -> Iterator[None]:
    """In-memory SQLite standing in for Postgres, same pattern as test_pipeline.py."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    with patch("app.db.session.get_sync_session_maker", return_value=session_maker):
        yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_sar_ndvi_query_deterministically_abstains_end_to_end():
    """F15: a genuinely unanswerable real SAR+NDVI query abstains cleanly, never crashes."""
    if not S1_PATH.exists():
        pytest.skip(f"real Sen1Floods11 fixture not present under {FIXTURES_DIR}")

    upload = PipelineUpload(
        id="sar-1",
        filename="Bolivia_103757_S1Hand.tif",
        content_type="image/tiff",
        content=S1_PATH.read_bytes(),
        modality=Modality.SAR,
    )
    # Stands in for the real model's actual confident, fabricated NDVI answer
    # (see module docstring) -- a hallucination this abstention path must
    # catch regardless of how plausible the model's own wording sounds.
    model = DeterministicVqaModel(
        answer=(
            "This image shows varying vegetation density. NDVI = (NIR - RED) / (NIR + RED). "
            "The darker areas have high NDVI and appear green."
        ),
        grounding="This image shows varying vegetation density.",
    )

    answer = run(query=QUERY, uploads=[upload], model=model)

    # Condition 1: typed abstention, not a plausible-sounding guess dressed as confident.
    assert answer.abstained is True
    assert answer.abstention_reason is not None
    assert "SENSOR_PHYSICAL_LIMITATION" in answer.abstention_reason
    assert answer.text == ""
    assert answer.confidence == 0.0

    # Condition 2: the rejecting rule is visible in the execution trace.
    verify_step = next(
        step for step in answer.trace.steps if step.action == "verification_completed"
    )
    assert verify_step.params["status"] == "abstained"
    rule_ids = {d["rule_id"] for d in verify_step.params["disagreements"]}
    assert "RULE-VERIFY-03" in rule_ids

    # Condition 3: no unsupported evidence/citation attached to the abstained answer.
    assert answer.evidence == []

    # Browser/API path stability: run() returns a normal Answer, never raises.
    actions = [step.action for step in answer.trace.steps]
    assert actions[-1] == "response_completed"
