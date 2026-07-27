from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str
    database_url: str
    jwt_secret: str
    otp_hmac_secret: str
    admin_api_key: str | None = None
    cors_allowed_origins: str = "http://127.0.0.1:5173"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
