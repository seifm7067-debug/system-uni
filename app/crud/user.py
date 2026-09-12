from app.models.user import User, UserRole
from app.schemas.tokenresponse import TokenResponse
from app.schemas.user import (
    UserCreate,
    UserLogin,
    UserRegister,
    UserSelfUpdate,
    UserUpdate,
)
from app.security.jwt import create_access_token
from app.security.password import hash_password, verify_password
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session


def ensure_admin_remains(
    db: Session, user: User, next_role: UserRole | None = None
) -> None:
    if user.role != UserRole.ADMIN or next_role == UserRole.ADMIN:
        return

    admin_ids = (
        db.execute(select(User.id).where(User.role == UserRole.ADMIN).with_for_update())
        .scalars()
        .all()
    )
    if len(admin_ids) <= 1:
        raise HTTPException(
            status_code=400, detail="Cannot remove the last admin account"
        )


def register_user(db: Session, user: UserRegister) -> User:

    data = user.model_dump(exclude={"password"})
    data["password_hash"] = hash_password(user.password)
    data["role"] = UserRole.GUEST
    data["email"] = data["email"].lower()
    new_user = User(**data)
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")
    except DataError:
        db.rollback()
        raise HTTPException(status_code=422, detail="Invalid user input data")


def create_user(db: Session, user: UserCreate) -> User:
    data = user.model_dump(exclude={"password"})
    data["password_hash"] = hash_password(user.password)
    data["email"] = data["email"].lower()
    new_user = User(**data)
    db.add(new_user)
    try:
        db.commit()
        db.refresh(new_user)
        return new_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")
    except DataError:
        db.rollback()
        raise HTTPException(status_code=422, detail="Invalid user input data")


def update_user(db: Session, user_update: UserUpdate, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_admin_remains(db, user, user_update.role)
    invalidates_tokens = False
    if user_update.username is not None:
        user.username = user_update.username
    if user_update.email is not None:
        user.email = user_update.email.lower()
    if user_update.password is not None:
        user.password_hash = hash_password(user_update.password)
        invalidates_tokens = True
    if user_update.role is not None:
        user.role = user_update.role
        invalidates_tokens = True
    if invalidates_tokens:
        user.token_version += 1
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")
    except DataError:
        db.rollback()
        raise HTTPException(status_code=422, detail="Invalid user input data")


def update_user_me(
    db: Session, user_update: UserSelfUpdate, current_user: User
) -> User:
    if user_update.username is not None:
        current_user.username = user_update.username
    if user_update.email is not None:
        current_user.email = user_update.email.lower()
    if user_update.password is not None:
        current_user.password_hash = hash_password(user_update.password)
        # Invalidate tokens issued before this password change.
        current_user.token_version += 1
    try:
        db.commit()
        db.refresh(current_user)
        return current_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username or email already exists")
    except DataError:
        db.rollback()
        raise HTTPException(status_code=422, detail="Invalid user input data")


def read_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def read_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    statement = select(User).order_by(User.id).offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_user(db: Session, user_id: int) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    ensure_admin_remains(db, user)

    db.delete(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Cannot delete user due to existing relationships"
        )
    return {"message": "User deleted successfully"}


_DUMMY_HASH = None


def _dummy_verify(password: str) -> bool:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy_password_for_timing")
    verify_password(password, _DUMMY_HASH)
    return False


def login_user(db: Session, user_login: UserLogin) -> TokenResponse:
    statement = select(User).where(User.email == user_login.email.lower())
    result = db.execute(statement)
    user = result.scalar_one_or_none()
    if user is None:
        _dummy_verify(user_login.password)
        raise HTTPException(status_code=401, detail="user or password incorrect")
    if verify_password(user_login.password, user.password_hash):
        return TokenResponse(
            access_token=create_access_token(user.id, user.token_version)
        )
    raise HTTPException(status_code=401, detail="user or password incorrect")
