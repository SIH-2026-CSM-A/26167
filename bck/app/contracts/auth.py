"""Auth request/response contracts — no password ever appears in an output schema."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_email(value: str) -> str:
    """Lowercase + strip at the boundary so uniqueness/lookup never depends on caller casing."""
    normalized = value.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("must be a valid email address")
    return normalized


class RegisterRequest(BaseModel):
    """New account request. `password` never leaves this schema."""

    model_config = ConfigDict(frozen=True)

    email: str
    password: str = Field(min_length=8)

    _normalize_email = field_validator("email")(_normalize_email)


class LoginRequest(BaseModel):
    """Existing-account credential check."""

    model_config = ConfigDict(frozen=True)

    email: str
    password: str = Field(min_length=1)

    _normalize_email = field_validator("email")(_normalize_email)


class UserPublic(BaseModel):
    """User shape safe to return to a client — structurally has no password field."""

    model_config = ConfigDict(frozen=True)

    id: str
    email: str
    is_verified: bool
    auth_provider: str
    created_at: datetime


class AuthResponse(BaseModel):
    """Issued on register/login: the user plus a bearer access token.

    The refresh token is never in this body — it's set as an httpOnly cookie by the route.
    """

    model_config = ConfigDict(frozen=True)

    user: UserPublic
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")
