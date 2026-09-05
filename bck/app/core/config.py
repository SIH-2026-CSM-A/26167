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


@lru_cache
def get_settings() -> Settings:
    return Settings()
