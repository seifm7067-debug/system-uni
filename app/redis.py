import logging
import ssl

from app.config import settings
from redis.exceptions import RedisError

from redis import Redis

logger = logging.getLogger(__name__)

_redis_client: Redis | None = None


def get_redis_client() -> Redis | None:
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        redis_url = settings.redis_url
        if redis_url.startswith("rediss://"):
            client = Redis.from_url(
                redis_url, decode_responses=True, ssl_cert_reqs=ssl.CERT_REQUIRED
            )
        else:
            client = Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        return _redis_client
    except RedisError as exc:
        logger.warning(
            "Redis server is unreachable (%s). Features depending on Redis will run in fallback mode.",
            exc,
        )
        return None


def check_redis_health() -> str:
    """Check Redis health and update connection state."""
    global _redis_client
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return "healthy"
        except RedisError:
            _redis_client = None
            return "unhealthy"
    client = get_redis_client()
    if client is None:
        return "unavailable"
    return "healthy"


def check_redis_url_health(redis_url: str) -> str:
    """Check a Redis endpoint without changing the cache client's connection."""
    try:
        if redis_url.startswith("rediss://"):
            client = Redis.from_url(
                redis_url, decode_responses=True, ssl_cert_reqs=ssl.CERT_REQUIRED
            )
        else:
            client = Redis.from_url(redis_url, decode_responses=True)
        client.ping()
        return "healthy"
    except (RedisError, ValueError) as exc:
        logger.warning("Redis health check failed: %s", exc)
        return "unhealthy"
