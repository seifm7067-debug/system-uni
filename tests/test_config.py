import pytest
from app.config import Settings
from pydantic import ValidationError


def test_production_settings_require_trusted_cors_origins():
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        Settings(
            app_environment="production",
            secret_key="a" * 32,
            database_url="sqlite://",
            rate_limit_storage_uri="redis://localhost:6379/1",
            rate_limit_fail_closed=True,
        )


def test_production_settings_require_fail_closed_redis_limiter():
    with pytest.raises(ValidationError, match="RATE_LIMIT_FAIL_CLOSED"):
        Settings(
            app_environment="production",
            secret_key="a" * 32,
            database_url="sqlite://",
            cors_origins=["https://app.example.com"],
            rate_limit_storage_uri="redis://localhost:6379/1",
        )


def test_production_settings_accept_distributed_limiter_and_cors():
    settings = Settings(
        app_environment="production",
        secret_key="a" * 32,
        database_url="sqlite://",
        cors_origins=["https://app.example.com"],
        rate_limit_storage_uri="redis://localhost:6379/1",
        rate_limit_fail_closed=True,
    )

    assert settings.app_environment == "production"
