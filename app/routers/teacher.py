from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud.teacher import (
    create_teacher,
    delete_teacher,
    read_teacher,
    read_teachers,
    update_teacher,
)
from app.database import get_db
from app.models.user import User
from app.schemas.teacher import TeacherCreate, TeacherResponseSchema, TeacherUpdate
from app.security.auth import require_admin, require_authenticated_user

router = APIRouter()


@router.post("/teachers/", response_model=TeacherResponseSchema, status_code=status.HTTP_201_CREATED)
def create_teacher_endpoint(
    teacher: TeacherCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_teacher(db, teacher)


@router.get("/teachers/{teacher_id}", response_model=TeacherResponseSchema)
def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_teacher(db, teacher_id)


@router.get("/teachers/", response_model=list[TeacherResponseSchema])
def get_teachers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_teachers(db, skip=skip, limit=limit)


@router.put("/teachers/{teacher_id}", response_model=TeacherResponseSchema)
def update_teacher_endpoint(
    teacher_id: int,
    teacher: TeacherUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_teacher(db, teacher, teacher_id)


@router.delete("/teachers/{teacher_id}")
def delete_teacher_endpoint(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_teacher(db, teacher_id)
