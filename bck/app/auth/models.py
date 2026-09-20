"""SQLAlchemy model for the users table.

A separate DeclarativeBase from app.db.models.Base: app.auth cannot import app.db (leaf
modules never import each other), so it owns its own Base. Both share one physical Postgres
database — alembic/env.py registers both Bases' metadata for migrations/autogenerate.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarative class for auth models."""


class User(Base):
    """A registered account. `hashed_password` is nullable — SSO users (Build 2) have none."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="password")
    provider_subject: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class RevokedToken(Base):
    """A refresh token's jti that was explicitly revoked (via logout) before its natural expiry.

    No FK to users: a revoked jti stays meaningful even if the user record is later removed.
    # ponytail: rows accumulate forever (no cleanup job exists in this repo). Correctness never
    # depends on cleanup since is_token_revoked filters expires_at > now(). If row count ever
    # matters, add `DELETE FROM revoked_tokens WHERE expires_at < now()` as an ops task.
    """

    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
