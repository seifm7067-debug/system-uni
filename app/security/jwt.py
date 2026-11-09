from datetime import UTC, datetime, timedelta

import jwt
from app.config import settings


def create_access_token(user_id: int, token_version: int = 0) -> str:
    payload = {
        "sub": str(user_id),
        "ver": token_version,
        "exp": datetime.now(UTC)
        + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> tuple[int, int] | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
        sub = payload.get("sub")
        ver = payload.get("ver", 0)
        if sub is None or not isinstance(ver, int) or ver < 0:
            return None
        return int(sub), ver
    except jwt.PyJWTError, ValueError, TypeError:
        return None
