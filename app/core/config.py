"""Shared settings. Secrets come from env / secret manager, never committed."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    api_version: str = "v1"
    database_url: str = "postgresql+asyncpg://pos:pos@localhost:5432/pos"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "pos-artifacts"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    ai_timeout_s: int = 30
    ai_circuit_breaker_s: int = 60


settings = Settings()
