"""JWT issue + validate. Access and refresh tokens share one encode/decode path,
distinguished only by their `type` claim and lifetime — never trust a token's claimed
type without checking it against what the caller expected.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt

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


def decode_token(token: str, expected_type: TokenType) -> str:
    """Return the token's subject (user id) if valid and of the expected type.

    Raises InvalidTokenError for anything else — expired, malformed, wrong secret,
    or a well-formed token of the *other* type (an access token can never be used
    where a refresh token is expected, and vice versa).
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
    return subject
