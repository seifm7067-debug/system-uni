import logging

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
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        _redis_client = client
        return _redis_client
    except RedisError as exc:
        logger.warning(
            "Redis server is unreachable (%s). Features depending on Redis will run in fallback mode.",
            exc,
        )
        return None
