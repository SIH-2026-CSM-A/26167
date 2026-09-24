"""Integration tests for /auth/* against a real TestClient + in-memory SQLite."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.auth.models import Base
from app.core.config import get_settings

client = TestClient(app)


@pytest.fixture(autouse=True)
def sqlite_auth_db() -> Iterator[None]:
    """In-memory SQLite for the users table, mirroring tests/api/test_main.py's pattern."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    client.cookies.clear()
    with (
        patch("app.auth.db.get_sync_session_maker", return_value=session_maker),
        patch("app.auth.db.get_fallback_session_maker", return_value=session_maker),
    ):
        yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _register(email: str = "demo@example.com", password: str = "correct-horse-battery") -> dict:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def test_register_succeeds_without_leaking_password():
    body = _register()
    assert body["user"]["email"] == "demo@example.com"
    assert "password" not in body["user"]
    assert "hashed_password" not in body["user"]
    assert body["access_token"]
    assert client.cookies.get("refresh_token") is not None


def test_register_duplicate_email_is_409():
    _register()
    response = client.post(
        "/auth/register", json={"email": "demo@example.com", "password": "another-password"}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["reason_code"] == "EMAIL_TAKEN"


def test_register_weak_password_is_422():
    response = client.post(
        "/auth/register", json={"email": "weak@example.com", "password": "short"}
    )
    assert response.status_code == 422


def test_login_success_issues_access_token_and_refresh_cookie():
    _register(email="login@example.com", password="correct-horse-battery")
    client.cookies.clear()
    response = client.post(
        "/auth/login", json={"email": "login@example.com", "password": "correct-horse-battery"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]
    assert "refresh_token" in response.cookies


def test_login_wrong_password_is_generic_401():
    _register(email="wrongpw@example.com", password="correct-horse-battery")
    response = client.post(
        "/auth/login", json={"email": "wrongpw@example.com", "password": "not-the-password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid email or password."


def test_login_unknown_email_is_the_same_generic_401():
    response = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever12345"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["message"] == "Invalid email or password."


def test_refresh_with_valid_cookie_issues_new_access_token():
    _register(email="refresh@example.com", password="correct-horse-battery")
    response = client.post("/auth/refresh")
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_without_cookie_is_401():
    client.cookies.clear()
    response = client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"]["reason_code"] == "INVALID_REFRESH_TOKEN"


def test_logout_clears_cookie():
    _register(email="logout@example.com", password="correct-horse-battery")
    response = client.post("/auth/logout")
    assert response.status_code == 204
    assert client.cookies.get("refresh_token") is None


def test_logout_revokes_the_refresh_token():
    _register(email="revoke@example.com", password="correct-horse-battery")
    refresh_cookie = client.cookies.get("refresh_token")
    logout_response = client.post("/auth/logout")
    assert logout_response.status_code == 204
    # Re-attach the pre-logout cookie value directly (the client's own cookie jar was just
    # cleared by the Set-Cookie on logout) to prove the token itself, not just the cookie,
    # is now invalid server-side.
    response = client.post("/auth/refresh", cookies={"refresh_token": refresh_cookie})
    assert response.status_code == 401
    assert response.json()["detail"]["reason_code"] == "INVALID_REFRESH_TOKEN"


def test_double_logout_does_not_crash():
    _register(email="double-logout@example.com", password="correct-horse-battery")
    assert client.post("/auth/logout").status_code == 204
    assert client.post("/auth/logout").status_code == 204


def test_me_with_valid_token_returns_user():
    body = _register(email="me@example.com", password="correct-horse-battery")
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_me_without_token_is_401():
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_with_expired_token_is_401():
    settings = get_settings()
    now = datetime.now(UTC)
    expired_token = jwt.encode(
        {
            "sub": "whoever",
            "type": "access",
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401


def test_login_demo_user_succeeds_without_prior_registration():
    client.cookies.clear()
    response = client.post(
        "/auth/login",
        json={"email": "demo@example.com", "password": "correct-horse-battery"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "demo@example.com"
    assert body["access_token"]
    assert "refresh_token" in response.cookies


def test_login_falls_back_to_sqlite_when_postgres_fails():
    from sqlalchemy.exc import OperationalError

    client.cookies.clear()
    with patch(
        "app.api.auth.get_sync_session",
        side_effect=OperationalError("connection failed", {}, None),
    ):
        response = client.post(
            "/auth/login",
            json={"email": "demo@example.com", "password": "correct-horse-battery"},
        )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "demo@example.com"


def test_register_falls_back_to_sqlite_when_postgres_fails():
    from sqlalchemy.exc import OperationalError

    client.cookies.clear()
    with patch(
        "app.api.auth.get_sync_session",
        side_effect=OperationalError("connection failed", {}, None),
    ):
        response = client.post(
            "/auth/register",
            json={"email": "fallback-reg@example.com", "password": "correct-horse-battery"},
        )
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "fallback-reg@example.com"


def test_refresh_falls_back_to_sqlite_when_postgres_fails():
    from sqlalchemy.exc import OperationalError

    _register(email="fallback-refresh@example.com", password="correct-horse-battery")
    with patch(
        "app.api.auth.get_sync_session",
        side_effect=OperationalError("connection failed", {}, None),
    ):
        response = client.post("/auth/refresh")
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_get_current_user_falls_back_to_sqlite_when_postgres_fails():
    from sqlalchemy.exc import OperationalError

    reg_body = _register(email="fallback-deps@example.com", password="correct-horse-battery")
    token = reg_body["access_token"]
    with patch(
        "app.api.deps.get_sync_session",
        side_effect=OperationalError("connection failed", {}, None),
    ):
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "fallback-deps@example.com"


def test_resilient_sync_engine_falls_back_to_sqlite(monkeypatch):
    from app.auth.db import get_sync_engine
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:54399/nonexistent")
    get_settings.cache_clear()
    get_sync_engine.cache_clear()
    try:
        engine = get_sync_engine()
        assert "sqlite" in str(engine.url)
    finally:
        get_sync_engine.cache_clear()
        get_settings.cache_clear()
