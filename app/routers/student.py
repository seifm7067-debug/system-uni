from app.crud.student import (
    create_student,
    delete_student,
    link_student_to_user,
    read_student,
    read_students,
    update_student,
)
from app.database import get_db
from app.models.user import User
from app.schemas.student import StudentCreate, StudentResponseSchema, StudentUpdate
from app.security.auth import require_admin, require_admin_or_user
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

router = APIRouter()


@router.post(
    "/students/",
    response_model=StudentResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_student_endpoint(
    student: StudentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_student(db, student)


@router.get("/students/{student_id}", response_model=StudentResponseSchema)
def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    return read_student(db, student_id, user=current_user)


@router.get("/students/", response_model=list[StudentResponseSchema])
def get_students(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    return read_students(db, user=current_user, skip=skip, limit=limit)


@router.put("/students/{student_id}", response_model=StudentResponseSchema)
def update_student_endpoint(
    student_id: int,
    student: StudentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_student(db, student, student_id)


@router.delete("/students/{student_id}")
def delete_student_endpoint(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_student(db, student_id)


@router.post(
    "/students/{student_id}/link-user/{user_id}", response_model=StudentResponseSchema
)
def link_student_user_endpoint(
    student_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return link_student_to_user(db, student_id, user_id)
