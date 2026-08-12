from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud.enrollment import (
    create_enrollment,
    delete_enrollment,
    read_enrollment,
    read_enrollments,
    update_enrollment,
)
from app.database import get_db
from app.models.user import User
from app.schemas import EnrollmentCreate, EnrollmentResponseSchema, EnrollmentUpdate
from app.security.auth import require_admin, require_admin_or_user

router = APIRouter()


@router.post("/enrollments/", response_model=EnrollmentResponseSchema, status_code=status.HTTP_201_CREATED)
def create_enrollment_endpoint(
    enrollment: EnrollmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_enrollment(db, enrollment)


@router.get("/enrollments/{enrollment_id}", response_model=EnrollmentResponseSchema)
def get_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    return read_enrollment(db, enrollment_id, user=current_user)


@router.get("/enrollments/", response_model=list[EnrollmentResponseSchema])
def get_enrollments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_user),
):
    return read_enrollments(db, user=current_user, skip=skip, limit=limit)


@router.put("/enrollments/{enrollment_id}", response_model=EnrollmentResponseSchema)
def update_enrollment_endpoint(
    enrollment_id: int,
    enrollment: EnrollmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_enrollment(db, enrollment, enrollment_id)


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment_endpoint(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_enrollment(db, enrollment_id)
