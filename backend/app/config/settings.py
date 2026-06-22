"""Typed application configuration loaded from environment."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings. Secrets never have defaults."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "juris-backend"
    environment: str = "development"
    cors_origins: list[str] = ["http://localhost:3000"]

    google_api_key: str = ""
    firebase_project_id: str = ""
    firebase_credentials: str = ""  # path to service account JSON
    firebase_storage_bucket: str = ""

    # Server — read by Dockerfile CMD; overridden by Cloud Run PORT injection or .env
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"

    # Optional observability (no-op until set)
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so env is parsed once."""
    return Settings()
