from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.tokens import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
    monkeypatch.setenv("COST_CEILING", "1")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-not-for-production")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_access_token_round_trips():
    token = create_access_token("user-1")
    assert decode_token(token, "access") == "user-1"


def test_refresh_token_round_trips():
    token = create_refresh_token("user-1")
    assert decode_token(token, "refresh") == "user-1"


def test_access_token_rejected_as_refresh():
    token = create_access_token("user-1")
    with pytest.raises(InvalidTokenError):
        decode_token(token, "refresh")


def test_refresh_token_rejected_as_access():
    token = create_refresh_token("user-1")
    with pytest.raises(InvalidTokenError):
        decode_token(token, "access")


def test_expired_token_rejected():
    settings = get_settings()
    now = datetime.now(UTC)
    expired_payload = {
        "sub": "user-1",
        "type": "access",
        "iat": now - timedelta(hours=1),
        "exp": now - timedelta(minutes=1),
    }
    expired_token = jwt.encode(
        expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    with pytest.raises(InvalidTokenError):
        decode_token(expired_token, "access")


def test_malformed_token_rejected():
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-real-token", "access")
