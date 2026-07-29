from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str
    database_url: str
    jwt_secret: SecretStr
    otp_hmac_secret: SecretStr
    admin_api_key: str | None = None
    cors_allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    log_level: str = "INFO"
    jwt_access_token_ttl_minutes: int = Field(default=60, gt=0)
    otp_ttl_seconds: int = Field(default=300, gt=0)
    otp_max_attempts: int = Field(default=5, gt=0)
    enable_demo_otp: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
