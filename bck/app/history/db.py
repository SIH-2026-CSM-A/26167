"""Synchronous SQLAlchemy engine and session provider for query-history persistence.

Mirrors app.auth.db's pattern (same DATABASE_URL, same asyncpg->psycopg scheme swap) rather
than importing it: app.history cannot import app.auth or app.db (leaf modules never import
each other), so it constructs its own sync session, same as every other leaf that needs one.
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
    settings = get_settings()
    url = str(settings.database_url)
    sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    return create_engine(sync_url)


@lru_cache
def get_sync_session_maker() -> sessionmaker[Session]:
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
