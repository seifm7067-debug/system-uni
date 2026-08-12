from app.models import CourseOffering
from app.schemas import CourseOfferingCreate, CourseOfferingUpdate
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session


def create_course_offering(
    db: Session, course_offering: CourseOfferingCreate
) -> CourseOffering:
    new_course_offering = CourseOffering(**course_offering.model_dump())
    db.add(new_course_offering)
    try:
        db.commit()
        db.refresh(new_course_offering)
        return new_course_offering
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate course offering constraint",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course offering data",
        )


def update_course_offering(
    db: Session,
    course_offering_update: CourseOfferingUpdate,
    course_offering_id: int,
) -> CourseOffering:
    statement = select(CourseOffering).where(CourseOffering.id == course_offering_id)
    result = db.execute(statement)
    course_offering = result.scalar_one_or_none()
    if course_offering is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course offering not found"
        )

    if course_offering_update.course_id is not None:
        course_offering.course_id = course_offering_update.course_id
    if course_offering_update.teacher_id is not None:
        course_offering.teacher_id = course_offering_update.teacher_id
    if course_offering_update.semester is not None:
        course_offering.semester = course_offering_update.semester
    if course_offering_update.academic_year is not None:
        course_offering.academic_year = course_offering_update.academic_year
    if course_offering_update.section is not None:
        course_offering.section = course_offering_update.section

    try:
        db.commit()
        db.refresh(course_offering)
        return course_offering
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Course offering constraint conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid course offering data",
        )


def read_course_offering(db: Session, course_offering_id: int) -> CourseOffering:
    statement = select(CourseOffering).where(CourseOffering.id == course_offering_id)
    result = db.execute(statement)
    course_offering = result.scalar_one_or_none()
    if course_offering is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course offering not found"
        )
    return course_offering


def read_course_offerings(
    db: Session, skip: int = 0, limit: int = 100
) -> list[CourseOffering]:
    statement = select(CourseOffering).offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_course_offering(db: Session, course_offering_id: int) -> dict:
    statement = select(CourseOffering).where(CourseOffering.id == course_offering_id)
    result = db.execute(statement)
    course_offering = result.scalar_one_or_none()
    if course_offering is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Course offering not found"
        )

    db.delete(course_offering)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete course offering due to active enrollments or schedules",
        )
    return {"message": "Course offering deleted successfully"}
