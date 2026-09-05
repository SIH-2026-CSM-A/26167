import pytest

from app.core.config import get_settings
from app.core.db import get_engine, get_session_maker


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "1")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_maker.cache_clear()
    yield
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_maker.cache_clear()


def test_engine_built_from_settings_without_connecting():
    engine = get_engine()
    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.database == "db"


def test_session_maker_bound_to_engine():
    maker = get_session_maker()
    assert maker.kw["bind"] is get_engine()
