from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

import logging


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Cortex"
    api_v1_prefix: str = "/api/v1"
    database_url: str = (
        "postgresql+asyncpg://cortex:cortex@localhost:5432/cortex"
    )
    frontend_origin: str = "http://localhost:5173"
    jwt_secret: str = "development-only-secret-change-me"
    jwt_issuer: str = "cortex-api"
    jwt_audience: str = "cortex-admin"
    access_token_minutes: int = 15
    refresh_session_days: int = 7
    guest_session_days: int = 30
    cookie_secure: bool = False
    admin_email: str | None = None
    admin_password: str | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)
logging.getLogger("cortex.requests").setLevel(logging.INFO)


@lru_cache
def get_settings() -> Settings:
    return Settings()
