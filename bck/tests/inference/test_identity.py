"""The expected model identity is written in three places; keep them from drifting apart."""

import re
from pathlib import Path

from app.inference.identity import EXPECTED_MODEL_IDENTITY, identity_mismatches
from app.models.internvl import DEFAULT_MODEL_ID, INTERNVL_REVISION

SPACE_APP = Path(__file__).resolve().parents[3] / "inference_space" / "app.py"


def test_expected_base_model_matches_the_pinned_local_loader():
    assert EXPECTED_MODEL_IDENTITY["base_model"] == DEFAULT_MODEL_ID
    assert EXPECTED_MODEL_IDENTITY["base_revision"] == INTERNVL_REVISION


def test_expected_hashes_match_the_space_startup_check():
    source = SPACE_APP.read_text(encoding="utf-8")
    adapter = re.search(r'EXPECTED_ADAPTER_SHA256 = "([0-9a-f]{64})"', source)
    bit = re.search(r'EXPECTED_BIT_SHA256 = "([0-9a-f]{64})"', source)
    assert adapter and bit
    assert EXPECTED_MODEL_IDENTITY["adapter_sha256"] == adapter.group(1)
    assert EXPECTED_MODEL_IDENTITY["bit_sha256"] == bit.group(1)


def test_identity_mismatches_names_the_differing_keys():
    recorded = dict(EXPECTED_MODEL_IDENTITY, bit_sha256="0" * 64)
    assert identity_mismatches(recorded, EXPECTED_MODEL_IDENTITY) == ["bit_sha256"]
    assert identity_mismatches(None, EXPECTED_MODEL_IDENTITY) == []
