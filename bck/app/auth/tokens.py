"""JWT issue + validate. Access and refresh tokens share one encode/decode path,
distinguished only by their `type` claim and lifetime — never trust a token's claimed
type without checking it against what the caller expected.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

from app.auth.db import get_sync_session
from app.auth.revocation import is_token_revoked
from app.core.config import get_settings

TokenType = Literal["access", "refresh"]


class InvalidTokenError(Exception):
    """A token is missing, malformed, expired, or not the expected type."""


def _create_token(user_id: str, token_type: TokenType, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    return _create_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes))


def create_refresh_token(user_id: str) -> str:
    settings = get_settings()
    return _create_token(user_id, "refresh", timedelta(days=settings.refresh_token_expire_days))


def get_token_claims(token: str, expected_type: TokenType) -> dict:
    """Decode and validate a token, returning its raw claims.

    Raises InvalidTokenError for anything invalid — expired, malformed, wrong secret,
    a well-formed token of the *other* type, a missing subject, or (refresh tokens
    only) a jti that has been revoked via /auth/logout.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as error:
        raise InvalidTokenError(str(error)) from error

    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"expected a {expected_type} token")
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("token has no subject")

    if expected_type == "refresh":
        jti = payload.get("jti")
        if not isinstance(jti, str) or not jti:
            raise InvalidTokenError("refresh token has no jti")
        with get_sync_session() as session:
            if is_token_revoked(session, jti):
                raise InvalidTokenError("refresh token has been revoked")

    return payload


def decode_token(token: str, expected_type: TokenType) -> str:
    """Return the token's subject (user id) if valid and of the expected type."""
    return get_token_claims(token, expected_type)["sub"]
