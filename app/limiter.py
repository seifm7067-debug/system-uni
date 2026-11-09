import logging
import ssl

from app.config import settings
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _build_limiter() -> Limiter:
    storage_uri = settings.rate_limit_storage_uri
    if storage_uri.startswith(("redis://", "rediss://")):
        try:
            import redis

            if storage_uri.startswith("rediss://"):
                client = redis.Redis.from_url(
                    storage_uri, ssl_cert_reqs=ssl.CERT_REQUIRED
                )
            else:
                client = redis.Redis.from_url(storage_uri)
            client.ping()
        except redis.RedisError as exc:
            if settings.rate_limit_fail_closed:
                raise RuntimeError(
                    "Redis is required for rate limiting but is unreachable"
                ) from exc
            logger.warning(
                "Redis unreachable at %s; falling back to in-memory rate limiting. "
                "Limits will not be shared across workers.",
                storage_uri,
            )
            storage_uri = "memory://"
    return Limiter(key_func=get_remote_address, storage_uri=storage_uri)


limiter = _build_limiter()
