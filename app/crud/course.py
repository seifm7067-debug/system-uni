from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Course
from app.schemas import CourseCreate, CourseUpdate


def create_course(db: Session, course: CourseCreate) -> Course:
    new_course = Course(**course.model_dump())
    db.add(new_course)
    try:
        db.commit()
        db.refresh(new_course)
        return new_course
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course code or name conflict in this department",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course data provided",
        )


def update_course(db: Session, course_update: CourseUpdate, course_id: int) -> Course:
    statement = select(Course).where(Course.id == course_id)
    result = db.execute(statement)
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    if course_update.name is not None:
        course.name = course_update.name
    if course_update.code is not None:
        course.code = course_update.code
    if course_update.department_id is not None:
        course.department_id = course_update.department_id

    try:
        db.commit()
        db.refresh(course)
        return course
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course code or name conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course data provided",
        )


def read_course(db: Session, course_id: int) -> Course:
    statement = select(Course).where(Course.id == course_id)
    result = db.execute(statement)
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


def read_courses(db: Session, skip: int = 0, limit: int = 100) -> list[Course]:
    statement = select(Course).offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_course(db: Session, course_id: int) -> dict:
    statement = select(Course).where(Course.id == course_id)
    result = db.execute(statement)
    course = result.scalar_one_or_none()
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")

    db.delete(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete course due to dependent course offerings",
        )
    return {"message": "Course deleted successfully"}
