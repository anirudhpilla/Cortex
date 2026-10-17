
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Cortex"
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    database_url: str = (
        "postgresql+asyncpg://cortex:cortex@localhost:5432/cortex"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    frontend_origin: str = "http://localhost:5173"
    trusted_proxy_ips: str = ""

    jwt_secret: SecretStr = SecretStr("development-only-secret-change-me")
    jwt_issuer: str = "cortex-api"
    jwt_audience: str = "cortex-admin"
    access_token_minutes: int = 15
    refresh_session_days: int = 7
    guest_session_days: int = 30
    cookie_secure: bool = False

    admin_email: str | None = None
    admin_password: SecretStr | None = None

    llm_provider: Literal["openai", "gemini", "ollama"] = "openai"
    llm_fallback_provider: Literal["openai", "gemini", "ollama"] = "ollama"

    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "qwen2.5:7b"
    ollama_embed_model: str = "nomic-embed-text"

    embedding_dimensions: int = Field(default=768, ge=1)
    embedding_model_version: str = "nomic-embed-text"

    chunk_size: int = 1000
    chunk_overlap: int = 150
    retrieval_k: int = 8
    candidate_k: int = 30
    max_query_evidence_tokens: int = 12000
    request_timeout_seconds: int = 60

    max_file_bytes: int = Field(default=2_000_000, ge=1)
    max_repository_files: int = Field(default=50_000, ge=1)
    max_repository_bytes: int = Field(default=2_000_000_000, ge=1)
    repository_base_path: str = "/app/documents"

    redis_url: str = "redis://localhost:6379/0"

    @model_validator(mode="after")
    def validate_settings(self):
        if self.access_token_minutes <= 0 or self.refresh_session_days <= 0:
            raise ValueError("Token lifetimes must be positive")

        if self.chunk_size <= 0 or not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("Invalid chunk size or overlap")

        if self.retrieval_k <= 0 or self.candidate_k < self.retrieval_k:
            raise ValueError("Invalid retrieval candidate limits")

        if self.embedding_dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")

        if self.database_pool_size <= 0 or self.database_max_overflow < 0:
            raise ValueError("Invalid database pool configuration")

        if self.environment == "production":
            if self.jwt_secret.get_secret_value() == "development-only-secret-change-me":
                raise ValueError("JWT_SECRET must be configured in production")
            if len(self.jwt_secret.get_secret_value()) < 32:
                raise ValueError("JWT_SECRET must contain at least 32 characters")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be enabled in production")
            if not self.frontend_origin.startswith("https://"):
                raise ValueError("FRONTEND_ORIGIN must use HTTPS in production")
            if self.llm_provider == "openai" and not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required")
            if self.llm_provider == "gemini" and not self.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required")

        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
