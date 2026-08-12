from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Enrollment, Student, User
from app.models.user import UserRole
from app.schemas import EnrollmentCreate, EnrollmentUpdate


def create_enrollment(db: Session, enrollment: EnrollmentCreate) -> Enrollment:
    new_enrollment = Enrollment(**enrollment.model_dump())
    db.add(new_enrollment)
    try:
        db.commit()
        db.refresh(new_enrollment)
        return new_enrollment
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student is already enrolled in this course offering or enrollment code duplicate",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid enrollment data provided",
        )


def update_enrollment(
    db: Session,
    enrollment_update: EnrollmentUpdate,
    enrollment_id: int,
) -> Enrollment:
    statement = select(Enrollment).where(Enrollment.id == enrollment_id)
    result = db.execute(statement)
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    if enrollment_update.student_id is not None:
        enrollment.student_id = enrollment_update.student_id
    if enrollment_update.course_offering_id is not None:
        enrollment.course_offering_id = enrollment_update.course_offering_id
    if enrollment_update.enrollment_code is not None:
        enrollment.enrollment_code = enrollment_update.enrollment_code
    if enrollment_update.grade is not None:
        enrollment.grade = enrollment_update.grade
    if enrollment_update.is_active is not None:
        enrollment.is_active = enrollment_update.is_active
    if enrollment_update.is_withdrawn is not None:
        enrollment.is_withdrawn = enrollment_update.is_withdrawn

    try:
        db.commit()
        db.refresh(enrollment)
        return enrollment
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Enrollment constraint violation",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid enrollment data provided",
        )


def read_enrollment(db: Session, enrollment_id: int, user: User) -> Enrollment:
    if user.role == UserRole.GUEST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    statement = select(Enrollment).where(Enrollment.id == enrollment_id)
    if user.role == UserRole.USER:
        statement = statement.join(Student).where(Student.user_id == user.id)

    result = db.execute(statement)
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    return enrollment


def read_enrollments(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
) -> list[Enrollment]:
    if user.role == UserRole.GUEST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    statement = select(Enrollment)
    if user.role == UserRole.USER:
        statement = statement.join(Student).where(Student.user_id == user.id)

    statement = statement.offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_enrollment(db: Session, enrollment_id: int) -> dict:
    statement = select(Enrollment).where(Enrollment.id == enrollment_id)
    result = db.execute(statement)
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment not found")

    db.delete(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete enrollment due to database constraints",
        )
    return {"message": "Enrollment deleted successfully"}
