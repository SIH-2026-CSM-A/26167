"""Environment-loaded settings. Nothing here is hardcoded — all values come from the process
environment (or a local .env file for dev) via pydantic-settings.
"""

from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    database_url: PostgresDsn
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
    frontend_origin: str = "http://localhost:5173"


@lru_cache
def get_settings() -> Settings:
    return Settings()
