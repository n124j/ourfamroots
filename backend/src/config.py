"""
Application configuration via pydantic-settings.
All values are read from environment variables (or .env file).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "OurFamRoots"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── Server ───────────────────────────────────────────────
    host: str = "0.0.0.0"  # nosec B104 — intentional: container listens on all interfaces
    port: int = 8000
    workers: int = 4

    # ── Database ─────────────────────────────────────────────
    database_url: PostgresDsn = Field(
        default="postgresql+asyncpg://ourfamroots:password@localhost:5432/ourfamroots"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600  # recycle connections after 1 hour
    database_echo_sql: bool = False    # set True in dev to log queries

    # ── Redis ────────────────────────────────────────────────
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_pool_size: int = 20

    # ── JWT ──────────────────────────────────────────────────
    jwt_secret_key: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 30
    jwt_refresh_token_remember_me_days: int = 90

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = True

    # ── AWS / S3 ─────────────────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket: str = "ourfamroots-media"
    s3_endpoint_url: str = ""          # override for MinIO / localstack
    s3_public_url: str = ""            # browser-accessible base URL (e.g. http://localhost:7002)
    s3_presigned_url_expire_seconds: int = 900

    # ── OAuth ────────────────────────────────────────────────
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    api_base_url: str = "http://localhost:8000"
    frontend_base_url: str = "http://localhost:5173"
    default_tenant_id: str = ""
    default_tenant_slug: str = "ourfamroots-system"

    # ── Email ────────────────────────────────────────────────
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "noreply@ourfamroots.com"

    # ── Rate Limiting ─────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_default_per_minute: int = 60

    # ── Web Push (VAPID) ─────────────────────────────────────
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_claims_email: str = "noreply@ourfamroots.com"

    # ── Email verification ───────────────────────────────────
    auto_verify_email: bool = False

    # ── Super Admin ──────────────────────────────────────────
    super_admin_email: str = ""

    # ── Sentry ───────────────────────────────────────────────
    sentry_dsn: str = ""

    @field_validator("jwt_secret_key", mode="before")
    @classmethod
    def _jwt_key_not_placeholder(cls, v: str) -> str:
        if v.startswith("CHANGE_ME"):
            raise ValueError("jwt_secret_key must be set to a real secret key.")
        return v

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_url_str(self) -> str:
        return str(self.database_url)

    @property
    def redis_url_str(self) -> str:
        return str(self.redis_url)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance. Use this everywhere; never instantiate Settings directly."""
    return Settings()
