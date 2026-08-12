from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud.courseschedule import (
    create_course_schedule,
    delete_course_schedule,
    read_course_schedule,
    read_course_schedules,
    update_course_schedule,
)
from app.database import get_db
from app.models.user import User
from app.schemas.courseschedule import (
    CourseScheduleCreate,
    CourseScheduleResponseSchema,
    CourseScheduleUpdate,
)
from app.security.auth import require_admin, require_authenticated_user

router = APIRouter()


@router.post("/course-schedules/", response_model=CourseScheduleResponseSchema, status_code=status.HTTP_201_CREATED)
def create_course_schedule_endpoint(
    course_schedule: CourseScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_course_schedule(db, course_schedule)


@router.get("/course-schedules/{course_schedule_id}", response_model=CourseScheduleResponseSchema)
def get_course_schedule(
    course_schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_course_schedule(db, course_schedule_id)


@router.get("/course-schedules/", response_model=list[CourseScheduleResponseSchema])
def get_course_schedules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_course_schedules(db, skip=skip, limit=limit)


@router.put("/course-schedules/{course_schedule_id}", response_model=CourseScheduleResponseSchema)
def update_course_schedule_endpoint(
    course_schedule_id: int,
    course_schedule: CourseScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_course_schedule(db, course_schedule, course_schedule_id)


@router.delete("/course-schedules/{course_schedule_id}")
def delete_course_schedule_endpoint(
    course_schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_course_schedule(db, course_schedule_id)
