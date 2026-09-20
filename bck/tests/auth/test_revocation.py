from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.models import Base
from app.auth.revocation import is_token_revoked, revoke_token


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


def test_unrevoked_jti_is_not_revoked(session: Session):
    assert is_token_revoked(session, "never-seen-jti") is False


def test_revoked_jti_is_revoked(session: Session):
    revoke_token(session, "some-jti", datetime.now(UTC) + timedelta(days=7))
    assert is_token_revoked(session, "some-jti") is True


def test_revoking_twice_does_not_raise(session: Session):
    expires = datetime.now(UTC) + timedelta(days=7)
    revoke_token(session, "dup-jti", expires)
    revoke_token(session, "dup-jti", expires)  # double logout with the same cookie
    assert is_token_revoked(session, "dup-jti") is True


def test_expired_revocation_is_excluded(session: Session):
    """Lazy cleanup: expires_at > now() means a jti whose natural expiry has already passed
    is no longer matched, even though its row is still physically present.
    """
    revoke_token(session, "long-gone-jti", datetime.now(UTC) - timedelta(days=1))
    assert is_token_revoked(session, "long-gone-jti") is False
