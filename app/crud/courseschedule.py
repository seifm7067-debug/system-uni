from app.models import CourseSchedule
from app.schemas import CourseScheduleCreate, CourseScheduleUpdate
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session


def _ensure_time_order(start_time, end_time) -> None:
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end_time must be strictly after start_time",
        )


def create_course_schedule(
    db: Session, course_schedule: CourseScheduleCreate
) -> CourseSchedule:
    _ensure_time_order(course_schedule.start_time, course_schedule.end_time)
    new_course_schedule = CourseSchedule(**course_schedule.model_dump())
    db.add(new_course_schedule)
    try:
        db.commit()
        db.refresh(new_course_schedule)
        return new_course_schedule
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Schedule conflict or constraint violation",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course schedule data",
        )


def update_course_schedule(
    db: Session,
    schedule_update: CourseScheduleUpdate,
    course_schedule_id: int,
) -> CourseSchedule:
    statement = select(CourseSchedule).where(CourseSchedule.id == course_schedule_id)
    result = db.execute(statement)
    course_schedule = result.scalar_one_or_none()
    if course_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course schedule not found"
        )

    start_time = schedule_update.start_time or course_schedule.start_time
    end_time = schedule_update.end_time or course_schedule.end_time
    _ensure_time_order(start_time, end_time)

    if schedule_update.day is not None:
        course_schedule.day = schedule_update.day
    if schedule_update.schedule_type is not None:
        course_schedule.schedule_type = schedule_update.schedule_type
    if schedule_update.start_time is not None:
        course_schedule.start_time = schedule_update.start_time
    if schedule_update.end_time is not None:
        course_schedule.end_time = schedule_update.end_time
    if schedule_update.room is not None:
        course_schedule.room = schedule_update.room
    if schedule_update.course_offering_id is not None:
        course_schedule.course_offering_id = schedule_update.course_offering_id

    try:
        db.commit()
        db.refresh(course_schedule)
        return course_schedule
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Schedule conflict or constraint violation",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course schedule data",
        )


def read_course_schedule(db: Session, course_schedule_id: int) -> CourseSchedule:
    statement = select(CourseSchedule).where(CourseSchedule.id == course_schedule_id)
    result = db.execute(statement)
    course_schedule = result.scalar_one_or_none()
    if course_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course schedule not found"
        )
    return course_schedule


def read_course_schedules(
    db: Session, skip: int = 0, limit: int = 100
) -> list[CourseSchedule]:
    statement = (
        select(CourseSchedule).order_by(CourseSchedule.id).offset(skip).limit(limit)
    )
    result = db.execute(statement)
    return result.scalars().all()


def delete_course_schedule(db: Session, course_schedule_id: int) -> dict:
    statement = select(CourseSchedule).where(CourseSchedule.id == course_schedule_id)
    result = db.execute(statement)
    course_schedule = result.scalar_one_or_none()
    if course_schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course schedule not found"
        )

    db.delete(course_schedule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete course schedule due to constraints",
        )
    return {"message": "Course schedule deleted successfully"}
