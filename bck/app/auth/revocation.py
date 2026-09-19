"""Refresh-token revocation store. Only refresh tokens are checked against this (access tokens
are short-lived and unaffected) — see decode_token in tokens.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import RevokedToken


def revoke_token(session: Session, jti: str, expires_at: datetime) -> None:
    """Insert a jti into the revoked set. Idempotent: revoking twice (e.g. a double logout with
    the same cookie) must not raise.
    """
    session.add(RevokedToken(jti=jti, expires_at=expires_at))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()


def is_token_revoked(session: Session, jti: str) -> bool:
    row = session.execute(
        select(RevokedToken).where(
            RevokedToken.jti == jti,
            RevokedToken.expires_at > datetime.now(UTC),
        )
    ).scalar_one_or_none()
    return row is not None
