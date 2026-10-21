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
    # boto3 reads AWS_*-style names; S3_* keys in .env.example were dead (I37).
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    oidc_issuer: str = ""
    oidc_audience: str = ""
    web_origin: str = "http://localhost:3000"
    # True when a reverse proxy fronts the API. Only then is
    # `X-Forwarded-For` believed: trusting it unconditionally would let a
    # client forge its address and walk past the rate limit.
    trusted_proxy: bool = False
    ai_timeout_s: int = 30
    ai_circuit_breaker_s: int = 60
    # Real AI provider (B49): when a base URL is configured, AI touchpoints
    # call it server-side through run_with_fallback + the hallucination scan;
    # empty = deterministic notes only (dev default).
    ai_primary_base_url: str = ""
    ai_primary_api_key: str = ""
    ai_primary_model: str = ""
    ai_fallback_base_url: str = ""
    ai_fallback_api_key: str = ""
    ai_fallback_model: str = ""
    # Transport-gated message delivery: when set, approved outbox messages
    # really send (POST JSON); empty = messages stay queued (dev default).
    outbox_webhook_url: str = ""

    def validate_auth(self) -> None:
        """Fail hard at boot when production has no OIDC issuer/audience: a
        production deployment authenticates through the IdP. Also refuses a
        silent half-config (issuer set, audience empty)."""
        if self.oidc_issuer and not self.oidc_audience:
            raise RuntimeError("OIDC_ISSUER is set but OIDC_AUDIENCE is empty")
        if self.app_env == "production" and not (self.oidc_issuer and self.oidc_audience):
            raise RuntimeError(
                "production requires OIDC_ISSUER and OIDC_AUDIENCE; "
                "email-and-password sessions are for local and test use"
            )


settings = Settings()
settings.validate_auth()
