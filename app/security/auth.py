from collections.abc import Callable

from app.database import get_db
from app.models.user import User, UserRole
from app.security.jwt import decode_access_token
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated"
        )

    decoded = decode_access_token(credentials.credentials)
    if decoded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    user_id, token_version = decoded
    user = db.get(User, user_id)
    if user is None or user.token_version != token_version:
        # Deleted user or credentials/role changed after this token was issued.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token"
        )
    return user


def require_roles(*allowed_roles: UserRole) -> Callable:
    def authorize(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="forbidden"
            )
        return user

    return authorize


require_admin = require_roles(UserRole.ADMIN)
require_admin_or_user = require_roles(UserRole.ADMIN, UserRole.USER)
require_authenticated_user = require_roles(
    UserRole.ADMIN, UserRole.USER, UserRole.GUEST
)
