"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
ENVIRONMENT_SELECTOR = "VKCA_ENV"
DEFAULT_ENV_FILE = ROOT_DIR / ".env"
TEST_ENV_FILE = ROOT_DIR / ".env.test"


def get_settings_env_file(environment: str | None = None) -> Path:
    """Select the settings file for an explicit runtime environment."""

    selected_environment = (
        os.getenv(ENVIRONMENT_SELECTOR) if environment is None else environment
    )
    if selected_environment is not None and selected_environment.casefold() == "test":
        return TEST_ENV_FILE
    return DEFAULT_ENV_FILE


class Settings(BaseSettings):
    """Runtime settings for the backend service."""

    database_url: PostgresDsn
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    refresh_inactivity_days: int = 7
    password_min_length: int = 12
    password_max_length: int = 128

    model_config = SettingsConfigDict(
        env_file=get_settings_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()  # type: ignore[call-arg]
