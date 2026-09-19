"""Synchronous SQLAlchemy engine and session provider for auth persistence.

Mirrors app.db.session's pattern (same DATABASE_URL, same asyncpg->psycopg scheme swap) rather
than importing it: app.auth cannot import app.db (leaf modules never import each other), so each
leaf that needs a sync session constructs its own — the same duplication already exists between
app.core.db (async) and app.db.session (sync).
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
