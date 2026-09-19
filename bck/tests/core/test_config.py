import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "2.5")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-not-for-production")
    settings = Settings(_env_file=None)
    assert settings.cost_ceiling == 2.5
    assert settings.log_level == "INFO"
    assert settings.titiler_base_url == "http://localhost:8001"


def test_settings_custom_titiler_base_url(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "2.5")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.setenv("TITILER_BASE_URL", "http://titiler.internal:8080")
    settings = Settings(_env_file=None)
    assert settings.titiler_base_url == "http://titiler.internal:8080"


def test_settings_requires_cost_ceiling(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-not-for-production")
    monkeypatch.delenv("COST_CEILING", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_non_positive_cost_ceiling(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "0")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-not-for-production")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_requires_jwt_secret_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "2.5")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_rejects_trivially_short_jwt_secret_key(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "2.5")
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
