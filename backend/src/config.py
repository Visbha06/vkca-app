"""Application configuration loaded from environment variables."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import (
    Field,
    PostgresDsn,
    RedisDsn,
    SecretStr,
    field_validator,
    model_validator,
)
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

    # Background processing settings. Resources are created by their runtime
    # boundaries, never while Settings is imported.
    redis_url: RedisDsn = RedisDsn("redis://localhost:6379/0")
    background_queue_name: str = Field(
        default="vkca-background", min_length=1, max_length=64
    )
    background_worker_max_jobs: int = Field(default=4, ge=1, le=64)
    background_job_timeout_seconds: float = Field(default=300.0, gt=0, le=3_600)
    background_max_attempts: int = Field(default=5, ge=1, le=20)
    background_retry_base_seconds: float = Field(default=5.0, gt=0, le=3_600)
    background_retry_max_seconds: float = Field(default=300.0, gt=0, le=86_400)
    background_retry_jitter_seconds: float = Field(default=5.0, ge=0, le=60)
    background_dispatch_batch_size: int = Field(default=50, ge=1, le=500)
    background_dispatch_poll_seconds: float = Field(default=5.0, gt=0, le=300)
    background_claim_lease_seconds: int = Field(default=120, ge=1, le=3_600)
    background_completed_retention_days: int = Field(default=7, ge=1, le=3_650)
    background_dead_retention_days: int = Field(default=30, ge=1, le=3_650)

    # RAG provider and bounded pipeline settings. Provider clients are created
    # by the RAG service boundary, never while Settings is imported.
    rag_embedding_provider: str = "fake"
    rag_embedding_model: str = "gemini-embedding-001"
    rag_embedding_dimension: int = Field(default=1536, ge=1536, le=1536)
    rag_embedding_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    rag_embedding_batch_size: int = Field(default=32, ge=1, le=256)
    rag_chunking_version: str = "rag-chunk-v1"
    rag_chunk_max_characters: int = Field(default=4000, ge=256, le=16_000)
    rag_chunk_context_characters: int = Field(default=240, ge=0, le=2_000)
    rag_query_max_characters: int = Field(default=1_000, ge=1, le=8_000)
    rag_result_limit_default: int = Field(default=5, ge=0, le=100)
    rag_result_limit_max: int = Field(default=20, ge=1, le=100)
    gemini_api_key: SecretStr | None = None

    @field_validator(
        "rag_embedding_provider",
        "rag_embedding_model",
        "rag_chunking_version",
        "background_queue_name",
    )
    @classmethod
    def validate_non_empty_rag_setting(cls, value: str) -> str:
        """Reject blank provider identifiers while retaining exact casing."""

        normalized = value.strip()
        if not normalized:
            raise ValueError("Configuration identifiers must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_rag_result_bounds(self) -> "Settings":
        """Keep result and initial Gemini profile settings mutually compatible."""

        if self.rag_result_limit_default > self.rag_result_limit_max:
            raise ValueError(
                "RAG_RESULT_LIMIT_DEFAULT must not exceed RAG_RESULT_LIMIT_MAX"
            )
        provider = self.rag_embedding_provider.casefold()
        if provider == "gemini" and self.rag_embedding_model != "gemini-embedding-001":
            raise ValueError(
                "The Gemini provider requires RAG_EMBEDDING_MODEL=gemini-embedding-001"
            )
        if self.background_retry_max_seconds < self.background_retry_base_seconds:
            raise ValueError(
                "BACKGROUND_RETRY_MAX_SECONDS must not be below "
                "BACKGROUND_RETRY_BASE_SECONDS"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=get_settings_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()  # type: ignore[call-arg]
