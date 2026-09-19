"""Auth routes — thin, calls app.auth only. Mirrors main.py's route style."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from app.api.deps import get_current_user
from app.auth import (
    InvalidTokenError,
    User,
    UserExistsError,
    create_access_token,
    create_refresh_token,
    create_user,
    decode_token,
    get_sync_session,
    get_token_claims,
    get_user_by_email,
    get_user_by_id,
    hash_password,
    revoke_token,
    verify_password,
)
from app.contracts import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from app.core.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE_NAME = "refresh_token"

_INVALID_CREDENTIALS_DETAIL = {
    "message": "Invalid email or password.",
    "reason_code": "INVALID_CREDENTIALS",
    "suggested_action": "Check your email and password and try again.",
}
_INVALID_REFRESH_DETAIL = {
    "message": "Session expired or invalid.",
    "reason_code": "INVALID_REFRESH_TOKEN",
    "suggested_action": "Log in again.",
}


def _issue_tokens(response: Response, user: User) -> AuthResponse:
    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/auth",
    )
    return AuthResponse(
        user=UserPublic(
            id=user.id,
            email=user.email,
            is_verified=user.is_verified,
            auth_provider=user.auth_provider,
            created_at=user.created_at,
        ),
        access_token=access_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(payload: RegisterRequest, response: Response) -> AuthResponse:
    with get_sync_session() as session:
        try:
            user = create_user(
                session,
                email=payload.email,
                hashed_password=hash_password(payload.password),
            )
        except UserExistsError as error:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "An account with this email already exists.",
                    "reason_code": "EMAIL_TAKEN",
                    "suggested_action": "Log in instead, or use a different email.",
                },
            ) from error
        session.expunge(user)
    return _issue_tokens(response, user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    with get_sync_session() as session:
        user = get_user_by_email(session, payload.email)
        if user is not None:
            session.expunge(user)
    if (
        user is None
        or user.hashed_password is None
        or not verify_password(payload.password, user.hashed_password)
    ):
        raise HTTPException(status_code=401, detail=_INVALID_CREDENTIALS_DETAIL)
    return _issue_tokens(response, user)


@router.post("/refresh", response_model=AuthResponse)
def refresh(
    response: Response, refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME)
) -> AuthResponse:
    if refresh_token is None:
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH_DETAIL)
    try:
        user_id = decode_token(refresh_token, "refresh")
    except InvalidTokenError as error:
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
        raise HTTPException(status_code=401, detail=_INVALID_REFRESH_DETAIL) from error

    with get_sync_session() as session:
        user = get_user_by_id(session, user_id)
        if user is None:
            response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")
            raise HTTPException(status_code=401, detail=_INVALID_REFRESH_DETAIL)
        session.expunge(user)
    return _issue_tokens(response, user)


@router.post("/logout", status_code=204)
def logout(
    response: Response, refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME)
) -> None:
    if refresh_token is not None:
        try:
            claims = get_token_claims(refresh_token, "refresh")
        except InvalidTokenError:
            claims = None
        if claims is not None:
            with get_sync_session() as session:
                revoke_token(session, claims["jti"], datetime.fromtimestamp(claims["exp"], UTC))
    response.delete_cookie(REFRESH_COOKIE_NAME, path="/auth")


@router.get("/me", response_model=UserPublic)
def me(user: User | None = Depends(get_current_user)) -> UserPublic:
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Missing or invalid access token.",
                "reason_code": "UNAUTHORIZED",
                "suggested_action": "Log in and retry with a valid Authorization: Bearer header.",
            },
        )
    return UserPublic(
        id=user.id,
        email=user.email,
        is_verified=user.is_verified,
        auth_provider=user.auth_provider,
        created_at=user.created_at,
    )
