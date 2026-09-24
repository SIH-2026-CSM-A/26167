"""Environment-loaded settings. Nothing here is hardcoded — all values come from the process
environment (or a local .env file for dev) via pydantic-settings.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Normalize DATABASE_URL for SQLAlchemy 2.0 usage, mapping postgres:// to postgresql://."""
    url = url.strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Settings(BaseSettings):
    """Process-wide configuration.

    `cost_ceiling` is a hard stop, not a warning: it is the maximum USD spend a single paid-API
    call path (currently only the optional Bhashini voice input, per AGENTS.md's "Cost ceilings"
    section) is allowed to reach before the caller must refuse the request rather than proceed.
    Enforcement lives in the calling module, not here — this contract only guarantees that the
    ceiling is always read from the environment and is never silently defaulted, so a missing
    value fails startup instead of falling back to an invented number.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(
        default="postgresql+psycopg://satquery:satquery_local_dev@localhost:5432/satquery"
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return normalize_database_url(value)
        return str(value)

    cost_ceiling: float = Field(gt=0)
    log_level: str = "INFO"
    titiler_base_url: str = "http://localhost:8001"

    jwt_secret_key: str = Field(min_length=16)
    """Signing secret for access/refresh JWTs. No default and a minimum length — like
    database_url and cost_ceiling, a missing or trivially-short value fails startup
    rather than signing tokens with a guessable fallback.
    """
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    auth_required: bool = True
    """Gates POST /query behind a valid access token. Only meant to be disabled for local
    pipeline testing without standing up auth end to end — never in a deployed environment.
    """
    auth_cookie_secure: bool = False
    """Secure flag on the refresh-token cookie. False for local http dev; must be True
    wherever the app is served over https.
    """
    frontend_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"]
    )
    """CORS allow-list and OAuth redirect targets. Comma-separated in the env var
    (`FRONTEND_ORIGINS=http://a,http://b`) so different machines/networks (e.g. a WSL
    172.x address alongside localhost) can be tested without editing code or restarting
    with a code change. `NoDecode` skips pydantic-settings' default JSON-array parsing
    for list fields, so the validator below can split the plain comma-separated string.
    """

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    """Google OAuth. All three optional/None-default: the app must boot without them, and
    /auth/google/* returns a clean 503 when any is unset rather than failing at startup.
    """

    isro_client_id: str | None = None
    isro_client_secret: str | None = None
    isro_auth_url: str | None = None
    isro_token_url: str | None = None
    isro_userinfo_url: str | None = None
    isro_redirect_uri: str | None = None
    """ISRO/Bhuvan CAS SSO. Real authorization-code flow, pointed at these config slots — no
    credentials exist yet (Bhuvan requires ISRO to register the app). All optional/None-default;
    /auth/isro/* returns a clean 503 until every one of these is set.
    """


@lru_cache
def get_settings() -> Settings:
    return Settings()
