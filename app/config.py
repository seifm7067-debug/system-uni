from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    secret_key: str
    access_token_expire_minutes: int = 30
    database_url: str
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: list[str] = []
    rate_limit_storage_uri: str = "memory://"

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
