"""FastAPI auth dependencies — thin, calls app.auth only."""

from __future__ import annotations

from fastapi import Header, HTTPException

from app.auth import InvalidTokenError, User, decode_token, get_sync_session, get_user_by_id
from app.core.config import get_settings

_UNAUTHORIZED_DETAIL = {
    "message": "Missing or invalid access token.",
    "reason_code": "UNAUTHORIZED",
    "suggested_action": "Log in and retry with a valid Authorization: Bearer header.",
}


def get_current_user(authorization: str | None = Header(default=None)) -> User | None:
    """Resolve the bearer access token to a User. Returns None when AUTH_REQUIRED is off.

    401s on anything else: no header, malformed header, expired/invalid token, or a token
    whose subject no longer resolves to a user.
    """
    if not get_settings().auth_required:
        return None
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED_DETAIL)
    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = decode_token(token, "access")
    except InvalidTokenError as error:
        raise HTTPException(status_code=401, detail=_UNAUTHORIZED_DETAIL) from error

    with get_sync_session() as session:
        user = get_user_by_id(session, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail=_UNAUTHORIZED_DETAIL)
        session.expunge(user)
    return user
