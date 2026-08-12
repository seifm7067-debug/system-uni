from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.crud.student import get_current_student
from app.crud.user import (
    delete_user,
    login_user,
    read_user,
    read_users,
    register_user,
    update_user,
    update_user_me,
)
from app.database import get_db
from app.limiter import limiter
from app.models.user import User, UserRole
from app.schemas.student import StudentResponseSchema
from app.schemas.tokenresponse import TokenResponse
from app.schemas.user import (
    UserLogin,
    UserRegister,
    UserResponse,
    UserSelfUpdate,
    UserUpdate,
)
from app.security.auth import get_current_user, require_admin

router = APIRouter()


@router.get("/users/me", response_model=UserResponse)
def get_current_user_endpoint(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/users/me", response_model=UserResponse)
def update_current_user_endpoint(
    user_update: UserSelfUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_user_me(db, user_update, current_user)


@router.get("/users/me/student", response_model=StudentResponseSchema)
def get_current_student_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role == UserRole.GUEST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    student = get_current_student(current_user.id, db)
    if student is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student record not found")
    return student


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return read_user(db, user_id)


@router.get("/users/", response_model=list[UserResponse])
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return read_users(db, skip=skip, limit=limit)


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user_endpoint(
    user_id: int,
    user: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return update_user(db, user, user_id)


@router.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return delete_user(db, user_id)


@router.post("/users/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register_user_endpoint(
    request: Request,
    user: UserRegister,
    db: Session = Depends(get_db),
):
    return register_user(db, user)


@router.post("/users/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login_user_endpoint(
    request: Request,
    user_login: UserLogin,
    db: Session = Depends(get_db),
):
    return login_user(db, user_login)
