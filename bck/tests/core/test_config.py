import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "2.5")
    settings = Settings(_env_file=None)
    assert settings.cost_ceiling == 2.5
    assert settings.log_level == "INFO"


def test_settings_requires_cost_ceiling(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.delenv("COST_CEILING", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_non_positive_cost_ceiling(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "0")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
