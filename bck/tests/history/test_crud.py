from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.history.crud import list_recent_for_user, record_query
from app.history.models import Base


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    maker = sessionmaker(bind=engine, expire_on_commit=False)
    with maker() as db_session:
        yield db_session
    engine.dispose()


def _record(session: Session, user_id: str | None, query_text: str) -> None:
    record_query(
        session,
        user_id=user_id,
        query_text=query_text,
        answer_text="answer",
        confidence=0.9,
        modality="optical",
    )


def test_list_recent_for_user_is_scoped_to_that_user(session: Session):
    _record(session, "user-a", "query A1")
    _record(session, "user-b", "query B1")

    rows = list_recent_for_user(session, user_id="user-a")

    assert len(rows) == 1
    assert rows[0].query_text == "query A1"


def test_list_recent_for_user_is_newest_first(session: Session):
    _record(session, "user-a", "first")
    _record(session, "user-a", "second")

    rows = list_recent_for_user(session, user_id="user-a")

    assert [row.query_text for row in rows] == ["second", "first"]


def test_list_recent_for_user_respects_limit(session: Session):
    for i in range(25):
        _record(session, "user-a", f"query {i}")

    rows = list_recent_for_user(session, user_id="user-a", limit=20)

    assert len(rows) == 20


def test_list_recent_for_user_empty_for_unknown_user(session: Session):
    _record(session, "user-a", "query A1")

    rows = list_recent_for_user(session, user_id="user-nobody")

    assert rows == []


def test_record_query_tolerates_none_user_id(session: Session):
    _record(session, None, "anonymous query")

    rows = list_recent_for_user(session, user_id="user-a")

    assert rows == []
