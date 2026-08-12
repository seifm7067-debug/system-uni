from app.crud.course import (
    create_course,
    delete_course,
    read_course,
    read_courses,
    update_course,
)
from app.database import get_db
from app.models.user import User
from app.schemas.course import CourseCreate, CourseResponseSchema, CourseUpdate
from app.security.auth import require_admin, require_authenticated_user
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

router = APIRouter()


@router.post(
    "/courses/",
    response_model=CourseResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_course_endpoint(
    course: CourseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_course(db, course)


@router.get("/courses/{course_id}", response_model=CourseResponseSchema)
def get_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_course(db, course_id)


@router.get("/courses/", response_model=list[CourseResponseSchema])
def get_courses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_courses(db, skip=skip, limit=limit)


@router.put("/courses/{course_id}", response_model=CourseResponseSchema)
def update_course_endpoint(
    course_id: int,
    course: CourseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_course(db, course, course_id)


@router.delete("/courses/{course_id}")
def delete_course_endpoint(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_course(db, course_id)
