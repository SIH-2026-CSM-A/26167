"""Test-wide isolation from a developer's bck/.env inference settings.

pydantic-settings reads bck/.env, so a machine configured to call the real inference Space
(INFERENCE_SPACE / HF_TOKEN in .env) would make "not configured" tests pass through to the
network. Process env vars take precedence over .env, so blanking them here keeps every test
offline; tests that need a configured Space set INFERENCE_SPACE themselves.
"""

from collections.abc import Iterator

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def no_inference_space_from_dotenv(monkeypatch) -> Iterator[None]:
    monkeypatch.setenv("INFERENCE_SPACE", "")
    monkeypatch.setenv("HF_TOKEN", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
