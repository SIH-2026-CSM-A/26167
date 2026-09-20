"""Integration tests for /auth/{google,isro}/* against a real TestClient + in-memory SQLite."""

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.auth.models import Base
from app.core.config import get_settings

client = TestClient(app, follow_redirects=False)


@pytest.fixture(autouse=True)
def sqlite_auth_db() -> Iterator[None]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    client.cookies.clear()
    with patch("app.auth.db.get_sync_session_maker", return_value=session_maker):
        yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def google_configured(monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mock_oauth_client(userinfo: dict) -> MagicMock:
    instance = MagicMock()
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?state=abc"
    instance.create_authorization_url.return_value = (auth_url, "abc")
    instance.fetch_token = AsyncMock(return_value={"access_token": "provider-access-token"})
    instance.get = AsyncMock(return_value=MagicMock(json=lambda: userinfo))
    return instance


def test_google_login_unconfigured_returns_503():
    response = client.get("/auth/google/login")
    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "GOOGLE_NOT_CONFIGURED"


def test_isro_login_unconfigured_returns_503():
    response = client.get("/auth/isro/login")
    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "ISRO_NOT_CONFIGURED"


def test_google_callback_unconfigured_returns_503():
    response = client.get("/auth/google/callback", params={"code": "x", "state": "y"})
    assert response.status_code == 503
    assert response.json()["detail"]["reason_code"] == "GOOGLE_NOT_CONFIGURED"


def test_google_login_redirects_to_google_when_configured(google_configured):
    mock_client = _mock_oauth_client({})
    with patch("app.api.oauth.AsyncOAuth2Client", return_value=mock_client):
        response = client.get("/auth/google/login")
    assert response.status_code in (302, 307)
    assert "accounts.google.com" in response.headers["location"]
    assert response.cookies.get("google_oauth_state") == "abc"


def test_google_callback_creates_user_and_issues_tokens(google_configured):
    userinfo = {"email": "new-google-user@example.com", "sub": "google-sub-1"}
    mock_client = _mock_oauth_client(userinfo)
    client.cookies.set("google_oauth_state", "abc")
    with patch("app.api.oauth.AsyncOAuth2Client", return_value=mock_client):
        response = client.get("/auth/google/callback", params={"code": "abc123", "state": "abc"})
    assert response.status_code == 303
    assert "access_token=" in response.headers["location"]
    assert response.cookies.get("refresh_token") is not None


def test_google_callback_state_mismatch_is_401(google_configured):
    client.cookies.set("google_oauth_state", "expected-state")
    params = {"code": "abc123", "state": "wrong-state"}
    response = client.get("/auth/google/callback", params=params)
    assert response.status_code == 401
    assert response.json()["detail"]["reason_code"] == "OAUTH_STATE_MISMATCH"


def test_google_callback_rejects_email_already_registered_with_password(google_configured):
    register_response = client.post(
        "/auth/register", json={"email": "shared@example.com", "password": "correct-horse-battery"}
    )
    assert register_response.status_code == 201

    mock_client = _mock_oauth_client({"email": "shared@example.com", "sub": "google-sub-2"})
    client.cookies.set("google_oauth_state", "abc")
    with patch("app.api.oauth.AsyncOAuth2Client", return_value=mock_client):
        response = client.get("/auth/google/callback", params={"code": "abc123", "state": "abc"})
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "EMAIL_REGISTERED_WITH_PASSWORD"
