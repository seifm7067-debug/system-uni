from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud.courseoffering import (
    create_course_offering,
    delete_course_offering,
    read_course_offering,
    read_course_offerings,
    update_course_offering,
)
from app.database import get_db
from app.models.user import User
from app.schemas.courseoffering import (
    CourseOfferingCreate,
    CourseOfferingResponseSchema,
    CourseOfferingUpdate,
)
from app.security.auth import require_admin, require_authenticated_user

router = APIRouter()


@router.post("/course-offerings/", response_model=CourseOfferingResponseSchema, status_code=status.HTTP_201_CREATED)
def create_course_offering_endpoint(
    course_offering: CourseOfferingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_course_offering(db, course_offering)


@router.get("/course-offerings/{course_offering_id}", response_model=CourseOfferingResponseSchema)
def get_course_offering(
    course_offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_course_offering(db, course_offering_id)


@router.get("/course-offerings/", response_model=list[CourseOfferingResponseSchema])
def get_course_offerings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_course_offerings(db, skip=skip, limit=limit)


@router.put("/course-offerings/{course_offering_id}", response_model=CourseOfferingResponseSchema)
def update_course_offering_endpoint(
    course_offering_id: int,
    course_offering: CourseOfferingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_course_offering(db, course_offering, course_offering_id)


@router.delete("/course-offerings/{course_offering_id}")
def delete_course_offering_endpoint(
    course_offering_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_course_offering(db, course_offering_id)
