from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_environment: Literal["development", "test", "production"] = "development"
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, ge=1)
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = Field(default_factory=list)
    rate_limit_storage_uri: str = "memory://"
    rate_limit_fail_closed: bool = False
    job_ttl_seconds: int = 86400
    job_processing_ttl: int = 1800
    job_poll_interval_seconds: float = Field(default=1.0, ge=0.1)
    job_lease_seconds: int = Field(default=120, ge=5)
    job_heartbeat_seconds: int = Field(default=30, ge=1)
    job_max_attempts: int = Field(default=3, ge=1)
    job_retry_base_seconds: int = Field(default=5, ge=1)
    worker_retry_attempts: int = Field(default=3, ge=1)
    jwt_algorithm: str = "HS256"

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        forbidden = ["replace", "changeme", "example", "placeholder", "your_", "insert"]
        v_lower = v.lower()
        if any(pattern in v_lower for pattern in forbidden):
            msg = (
                "SECRET_KEY contains a placeholder pattern. "
                "Generate a real key with: python -c 'import secrets; print(secrets.token_urlsafe(48))'"
            )
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        if self.app_environment != "production":
            return self
        if not self.cors_origins:
            raise ValueError("CORS_ORIGINS must contain at least one trusted origin")
        if not self.rate_limit_storage_uri.startswith(("redis://", "rediss://")):
            raise ValueError("production rate limiting requires a Redis storage URI")
        if not self.rate_limit_fail_closed:
            raise ValueError(
                "production rate limiting must set RATE_LIMIT_FAIL_CLOSED=true"
            )
        return self

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
