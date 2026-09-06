"""Synchronous SQLAlchemy engine and session provider for pipeline persistence.

Follows existing repository psycopg conventions while providing clean, request-scoped
synchronous database sessions suitable for execution inside pipeline threads.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_sync_engine() -> Engine:
    """Create or return the cached synchronous SQLAlchemy Engine."""
    settings = get_settings()
    return create_engine(str(settings.database_url))


@lru_cache
def get_sync_session_maker() -> sessionmaker[Session]:
    """Create or return the cached sessionmaker bound to the sync engine."""
    return sessionmaker(bind=get_sync_engine(), expire_on_commit=False)


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    maker = get_sync_session_maker()
    session = maker()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
