"""Google OAuth (real) + ISRO/Bhuvan CAS SSO (real authorization-code flow, config-slot
placeholder — no Bhuvan credentials exist yet; ISRO must register the app first). Both
providers share one shape via authlib's AsyncOAuth2Client. All config is optional/None-default
(app.core.config) so the app boots without credentials; each route 503s cleanly if its
provider isn't fully configured rather than failing at startup or hardcoding a URL that
doesn't work.
"""

from __future__ import annotations

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Cookie, HTTPException
from fastapi.responses import RedirectResponse

from app.api.auth import REFRESH_COOKIE_NAME
from app.auth import (
    User,
    create_access_token,
    create_refresh_token,
    create_user,
    get_sync_session,
    get_user_by_email,
    get_user_by_provider_subject,
)
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["oauth"])

_STATE_COOKIE_MAX_AGE = 600  # 10 minutes — only needs to outlive the redirect round trip

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

_GOOGLE_STATE_COOKIE = "google_oauth_state"
_ISRO_STATE_COOKIE = "isro_oauth_state"

_EMAIL_REGISTERED_WITH_PASSWORD_DETAIL = {
    "message": "email already registered with a password",
    "reason_code": "EMAIL_REGISTERED_WITH_PASSWORD",
    "suggested_action": "Log in with your password instead, or use a different account.",
}


def _require_google_configured(settings: Settings) -> None:
    if not (
        settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri
    ):
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Google sign-in not configured",
                "reason_code": "GOOGLE_NOT_CONFIGURED",
                "suggested_action": "Contact an administrator.",
            },
        )


def _require_isro_configured(settings: Settings) -> None:
    if not all(
        [
            settings.isro_client_id,
            settings.isro_client_secret,
            settings.isro_auth_url,
            settings.isro_token_url,
            settings.isro_userinfo_url,
            settings.isro_redirect_uri,
        ]
    ):
        raise HTTPException(
            status_code=503,
            detail={
                "message": "ISRO SSO not configured",
                "reason_code": "ISRO_NOT_CONFIGURED",
                "suggested_action": "Contact an administrator.",
            },
        )


def _redirect_with_tokens(settings: Settings, user: User) -> RedirectResponse:
    """Issue our tokens for an OAuth-authenticated user and hand them to the frontend via a
    redirect: access token + expiry as query params (one-time, read-and-discard by the
    frontend's /oauth/callback route), refresh token as the usual httpOnly /auth-scoped cookie.
    This is the redirect-flow counterpart to _issue_tokens in app.api.auth (used by the
    JSON-body password routes) — a real page navigation can't receive a JSON response body.
    """
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    query = (
        f"access_token={access_token}"
        f"&expires_in={settings.access_token_expire_minutes * 60}"
        "&token_type=bearer"
    )
    redirect_url = f"{settings.frontend_origins[0]}/oauth/callback?{query}"
    redirect = RedirectResponse(redirect_url, status_code=303)
    redirect.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/auth",
    )
    return redirect


def _find_or_create_oauth_user(*, email: str, subject: str, auth_provider: str) -> User:
    with get_sync_session() as session:
        user = get_user_by_provider_subject(session, subject)
        if user is None:
            existing = get_user_by_email(session, email)
            if existing is not None and existing.hashed_password is not None:
                # Reject rather than silently link: an OAuth provider proving control of an
                # email address does not prove the caller knows the existing account's
                # password. Silently linking here would let anyone who controls that email's
                # Google/ISRO account take over a pre-existing password account.
                raise HTTPException(status_code=409, detail=_EMAIL_REGISTERED_WITH_PASSWORD_DETAIL)
            user = create_user(
                session,
                email=email,
                hashed_password=None,
                auth_provider=auth_provider,
                provider_subject=subject,
                is_verified=True,  # the provider already verified this email
            )
        session.expunge(user)
    return user


@router.get("/google/login")
async def google_login() -> RedirectResponse:
    settings = get_settings()
    _require_google_configured(settings)
    client = AsyncOAuth2Client(
        settings.google_client_id,
        settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
        scope="openid email",
    )
    url, state = client.create_authorization_url(GOOGLE_AUTH_URL)
    redirect = RedirectResponse(url)
    redirect.set_cookie(
        _GOOGLE_STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=_STATE_COOKIE_MAX_AGE,
        path="/auth",
    )
    return redirect


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    google_oauth_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    settings = get_settings()
    _require_google_configured(settings)
    if not google_oauth_state or state != google_oauth_state:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "OAuth state mismatch.",
                "reason_code": "OAUTH_STATE_MISMATCH",
                "suggested_action": "Try signing in again.",
            },
        )

    client = AsyncOAuth2Client(
        settings.google_client_id,
        settings.google_client_secret,
        redirect_uri=settings.google_redirect_uri,
    )
    await client.fetch_token(GOOGLE_TOKEN_URL, code=code)
    userinfo = (await client.get(GOOGLE_USERINFO_URL)).json()

    user = _find_or_create_oauth_user(
        email=userinfo["email"], subject=userinfo["sub"], auth_provider="google"
    )
    return _redirect_with_tokens(settings, user)


@router.get("/isro/login")
async def isro_login() -> RedirectResponse:
    settings = get_settings()
    _require_isro_configured(settings)
    client = AsyncOAuth2Client(
        settings.isro_client_id,
        settings.isro_client_secret,
        redirect_uri=settings.isro_redirect_uri,
    )
    url, state = client.create_authorization_url(settings.isro_auth_url)
    redirect = RedirectResponse(url)
    redirect.set_cookie(
        _ISRO_STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=_STATE_COOKIE_MAX_AGE,
        path="/auth",
    )
    return redirect


@router.get("/isro/callback")
async def isro_callback(
    code: str,
    state: str,
    isro_oauth_state: str | None = Cookie(default=None),
) -> RedirectResponse:
    settings = get_settings()
    _require_isro_configured(settings)
    if not isro_oauth_state or state != isro_oauth_state:
        raise HTTPException(
            status_code=401,
            detail={
                "message": "OAuth state mismatch.",
                "reason_code": "OAUTH_STATE_MISMATCH",
                "suggested_action": "Try signing in again.",
            },
        )

    client = AsyncOAuth2Client(
        settings.isro_client_id,
        settings.isro_client_secret,
        redirect_uri=settings.isro_redirect_uri,
    )
    await client.fetch_token(settings.isro_token_url, code=code)
    userinfo = (await client.get(settings.isro_userinfo_url)).json()

    user = _find_or_create_oauth_user(
        email=userinfo["email"], subject=userinfo["sub"], auth_provider="isro"
    )
    return _redirect_with_tokens(settings, user)
