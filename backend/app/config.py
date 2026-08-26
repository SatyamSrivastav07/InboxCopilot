from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(RuntimeError):
    """Raised when a required runtime setting is missing."""


class Settings(BaseSettings):
    """Centralized, environment-backed application configuration."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        enable_decoding=False,
        extra="ignore",
        frozen=True,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    max_request_bytes: int = 1_000_000
    mistral_api_key: str | None = None
    mistral_model: str = "mistral-small-latest"
    frontend_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    frontend_url: str = "http://localhost:5173"
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/api/gmail/callback"
    gmail_token_file: Path = Path("token.json")
    database_url: str | None = None
    chroma_persist_directory: Path = Path("data/chromadb")
    chroma_collection_name: str = "inbox_emails"
    rag_top_k: int = 4
    rag_score_threshold: float = 0.2
    email_chunk_size: int = 1000
    email_chunk_overlap: int = 100
    reply_thread_max_chars: int = 12_000
    reply_thread_recent_messages: int = 8
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    cache_ttl_seconds: int = 60
    genai_max_retries: int = 3
    sync_lock_ttl_seconds: int = 30 * 60

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def split_origins(cls, value: str | tuple[str, ...] | list[str]) -> tuple[str, ...]:
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        return tuple(value)

    @field_validator("gmail_token_file", "chroma_persist_directory", mode="after")
    @classmethod
    def resolve_backend_paths(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return Path(__file__).resolve().parents[1] / value

    @field_validator("frontend_url", mode="after")
    @classmethod
    def normalize_frontend_url(cls, value: str) -> str:
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_runtime_shape(self) -> "Settings":
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test, or production.")
        if self.max_request_bytes < 1:
            raise ValueError("MAX_REQUEST_BYTES must be positive.")
        if self.cache_ttl_seconds < 1 or self.genai_max_retries < 1:
            raise ValueError("CACHE_TTL_SECONDS and GENAI_MAX_RETRIES must be positive.")
        return self

    def require_mistral_api_key(self) -> str:
        if not self.mistral_api_key:
            raise ConfigurationError(
                "MISTRAL_API_KEY is not configured. Copy .env.example to .env and add your key."
            )
        return self.mistral_api_key

    def require_google_oauth(self) -> tuple[str, str]:
        if not self.google_client_id or not self.google_client_secret:
            raise ConfigurationError(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and "
                "GOOGLE_CLIENT_SECRET in backend/.env."
            )
        return self.google_client_id, self.google_client_secret

    def require_database_url(self) -> str:
        if not self.database_url:
            raise ConfigurationError(
                "DATABASE_URL is not configured. Add the PostgreSQL connection URL to backend/.env."
            )
        return self.database_url

    def validate_production_requirements(self) -> None:
        if self.app_env != "production":
            return
        self.require_database_url()
        self.require_mistral_api_key()
        self.require_google_oauth()
        if "*" in self.frontend_origins:
            raise ConfigurationError("FRONTEND_ORIGINS cannot use wildcard origins in production.")
        if not self.frontend_url.startswith("https://"):
            raise ConfigurationError("FRONTEND_URL must use HTTPS in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()
