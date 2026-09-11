from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str
    access_token_expire_minutes: int = 30
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = []
    rate_limit_storage_uri: str = "memory://"
    job_ttl_seconds: int = 86400
    job_processing_ttl: int = 1800
    job_poll_interval_seconds: float = 1.0
    job_lease_seconds: int = 120
    job_heartbeat_seconds: int = 30
    job_max_attempts: int = 3
    job_retry_base_seconds: int = 5
    worker_retry_attempts: int = 3

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
