"""Synchronous SQLAlchemy engine and session provider for auth persistence.

Mirrors app.db.session's pattern (same DATABASE_URL, same asyncpg->psycopg scheme swap) rather
than importing it: app.auth cannot import app.db (leaf modules never import each other), so each
leaf that needs a sync session constructs its own — the same duplication already exists between
app.core.db (async) and app.db.session (sync).
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.auth.models import Base as AuthBase
from app.core.config import get_settings, sync_database_url

logger = logging.getLogger(__name__)


@lru_cache
def get_fallback_engine() -> Engine:
    """SQLite engine at settings.auth_fallback_db_path, with the auth tables created."""
    path = get_settings().auth_fallback_db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    AuthBase.metadata.create_all(bind=engine, checkfirst=True)
    return engine


@lru_cache
def get_sync_engine() -> Engine:
    """Postgres engine, or the SQLite fallback engine if a connect probe fails."""
    settings = get_settings()
    url = str(settings.database_url)
    sync_url = sync_database_url(url)
    if not sync_url.startswith("postgresql"):
        return create_engine(sync_url)
    engine = create_engine(sync_url, connect_args={"connect_timeout": 2})
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except (OperationalError, DBAPIError) as error:
        logger.warning("Postgres unreachable (%s); using SQLite auth fallback.", error)
        engine.dispose()
        return get_fallback_engine()
    return engine


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


@lru_cache
def get_fallback_session_maker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_fallback_engine(), expire_on_commit=False)


@contextmanager
def get_fallback_session() -> Generator[Session, None, None]:
    """Same as get_sync_session, but against the SQLite fallback database."""
    maker = get_fallback_session_maker()
    session = maker()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
