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

    # M3: document processing
    chunk_size_tokens:        int   = 512
    chunk_overlap_tokens:     int   = 50
    max_chunks_per_document:  int   = 1000
    retrieval_top_k:          int   = 5
    citation_score_threshold: float = 0.3

    # M5: voice
    stt_provider: str = "google_cloud"
    stt_model: str = "latest_long"
    voice_max_audio_seconds: int = 120
    voice_max_audio_bytes: int = 10 * 1024 * 1024
    tts_provider: str = "google_cloud"
    tts_voice_default: str = "en-IN-Neural2-A"
    tts_audio_encoding: str = "MP3"
    voice_max_synthesize_chars: int = 5000

    # Optional observability (no-op until set)
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Cached singleton so env is parsed once."""
    return Settings()
