from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.db import get_sync_session
from app.auth.models import Base
from app.auth.revocation import revoke_token
from app.auth.tokens import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_claims,
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


@pytest.fixture(autouse=True)
def sqlite_auth_db() -> Iterator[None]:
    """Refresh-token decode checks revocation via a DB read — give it an in-memory SQLite
    instead of the fake DATABASE_URL above, mirroring tests/api/test_auth.py's pattern.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    with patch("app.auth.db.get_sync_session_maker", return_value=session_maker):
        yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


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


def test_refresh_token_has_a_jti_claim():
    token = create_refresh_token("user-1")
    claims = get_token_claims(token, "refresh")
    assert isinstance(claims["jti"], str) and claims["jti"]


def test_revoked_refresh_token_is_rejected():
    token = create_refresh_token("user-1")
    claims = get_token_claims(token, "refresh")
    with get_sync_session() as session:
        revoke_token(session, claims["jti"], datetime.fromtimestamp(claims["exp"], UTC))
    with pytest.raises(InvalidTokenError):
        decode_token(token, "refresh")
