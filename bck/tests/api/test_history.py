"""Integration tests for GET /history against a real TestClient + in-memory SQLite.

Per-user scoping is the ship-safety-critical property here: a caller must never see another
user's rows.
"""

from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.main import app
from app.auth.models import Base as AuthBase
from app.history.crud import record_query
from app.history.models import Base as HistoryBase

client = TestClient(app)


@pytest.fixture(autouse=True)
def sqlite_history_db() -> Iterator[sessionmaker]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AuthBase.metadata.create_all(bind=engine)
    HistoryBase.metadata.create_all(bind=engine)
    session_maker = sessionmaker(bind=engine, expire_on_commit=False)
    client.cookies.clear()
    with (
        patch("app.auth.db.get_sync_session_maker", return_value=session_maker),
        patch("app.history.db.get_sync_session_maker", return_value=session_maker),
    ):
        yield session_maker
    AuthBase.metadata.drop_all(bind=engine)
    HistoryBase.metadata.drop_all(bind=engine)
    engine.dispose()


def _register(email: str) -> str:
    payload = {"email": email, "password": "correct-horse-battery"}
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_history_requires_auth():
    response = client.get("/history")
    assert response.status_code == 401
    assert response.json()["detail"]["reason_code"] == "UNAUTHORIZED"


def test_history_returns_only_the_caller_own_rows(sqlite_history_db: sessionmaker):
    token_a = _register("owner-a@example.com")
    token_b = _register("owner-b@example.com")
    user_a_id = client.get("/auth/me", headers={"Authorization": f"Bearer {token_a}"}).json()["id"]
    user_b_id = client.get("/auth/me", headers={"Authorization": f"Bearer {token_b}"}).json()["id"]

    with sqlite_history_db() as session:
        record_query(
            session,
            user_id=user_a_id,
            query_text="A's query",
            answer_text="A's answer",
            confidence=0.9,
            modality="optical",
        )
        record_query(
            session,
            user_id=user_b_id,
            query_text="B's query",
            answer_text="B's answer",
            confidence=0.8,
            modality="sar",
        )

    response_a = client.get("/history", headers={"Authorization": f"Bearer {token_a}"})
    assert response_a.status_code == 200
    body_a = response_a.json()
    assert len(body_a) == 1
    assert body_a[0]["query_text"] == "A's query"


def test_history_is_empty_for_a_fresh_user(sqlite_history_db: sessionmaker):
    token = _register("fresh@example.com")

    response = client.get("/history", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == []


def test_history_caps_at_twenty_rows(sqlite_history_db: sessionmaker):
    token = _register("prolific@example.com")
    user_id = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

    with sqlite_history_db() as session:
        for i in range(25):
            record_query(
                session,
                user_id=user_id,
                query_text=f"query {i}",
                answer_text="answer",
                confidence=0.9,
                modality="optical",
            )

    response = client.get("/history", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert len(response.json()) == 20
