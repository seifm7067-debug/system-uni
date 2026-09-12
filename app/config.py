from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = Field(default=30, ge=1)
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = []
    rate_limit_storage_uri: str = "memory://"
    job_ttl_seconds: int = 86400
    job_processing_ttl: int = 1800
    job_poll_interval_seconds: float = Field(default=1.0, ge=0.1)
    job_lease_seconds: int = Field(default=120, ge=5)
    job_heartbeat_seconds: int = Field(default=30, ge=1)
    job_max_attempts: int = Field(default=3, ge=1)
    job_retry_base_seconds: int = Field(default=5, ge=1)
    worker_retry_attempts: int = Field(default=3, ge=1)

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
