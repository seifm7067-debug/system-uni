import json

from app.models import Student, User
from app.models.user import UserRole
from app.redis import get_redis_client
from app.schemas import StudentCreate, StudentResponseSchema, StudentUpdate
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError


def _invalidate_student_cache(student_id: int) -> None:
    redis_client = get_redis_client()
    if redis_client is not None:
        redis_client.delete(f"student:{student_id}")


def create_student(db: Session, student: StudentCreate) -> Student:
    new_student = Student(**student.model_dump())
    db.add(new_student)
    try:
        db.commit()
        db.refresh(new_student)
        return new_student
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student email or constraint already exists",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid student data provided",
        )


def update_student(
    db: Session, student_update: StudentUpdate, student_id: int
) -> Student:
    statement = select(Student).where(Student.id == student_id)
    result = db.execute(statement)
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    if (
        student_update.version_id is not None
        and student.version_id != student_update.version_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student record has been modified by another transaction (version mismatch)",
        )

    if student_update.name is not None:
        student.name = student_update.name
    if student_update.department_id is not None:
        student.department_id = student_update.department_id
    if student_update.age is not None:
        student.age = student_update.age
    if student_update.email is not None:
        student.email = student_update.email

    _invalidate_student_cache(student_id)
    try:
        db.commit()
        db.refresh(student)
        return student
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student record has been modified by another transaction",
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student email or constraint conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid student data provided",
        )


def read_student(db: Session, student_id: int, user: User) -> StudentResponseSchema:
    redis = get_redis_client()
    cache_key = f"student:{student_id}"
    if user.role == UserRole.GUEST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if user.role == UserRole.ADMIN and redis:
        cached_student = redis.get(cache_key)
        if cached_student:
            student_dict = json.loads(cached_student)
            student_response = StudentResponseSchema.model_validate(student_dict)
            return student_response

    statement = select(Student).where(Student.id == student_id)
    if user.role == UserRole.USER:
        statement = statement.where(Student.user_id == user.id)

    result = db.execute(statement)
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    student_response = StudentResponseSchema.model_validate(student)
    if user.role == UserRole.ADMIN and redis:
        cache_student = student_response.model_dump(mode="json")
        student_json = json.dumps(cache_student)
        redis.set(cache_key, student_json, ex=60)

    return student_response


def read_students(
    db: Session,
    user: User,
    skip: int = 0,
    limit: int = 100,
) -> list[Student]:
    if user.role == UserRole.GUEST:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    statement = select(Student)
    if user.role == UserRole.USER:
        statement = statement.where(Student.user_id == user.id)

    statement = statement.offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_student(db: Session, student_id: int) -> dict:
    statement = select(Student).where(Student.id == student_id)
    result = db.execute(statement)
    student = result.scalar_one_or_none()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    db.delete(student)
    _invalidate_student_cache(student_id)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete student due to existing dependent records (e.g. enrollments)",
        )
    return {"message": "Student deleted successfully"}


def get_current_student(user_id: int, db: Session) -> Student | None:
    statement = select(Student).where(Student.user_id == user_id)
    result = db.execute(statement)
    return result.scalar_one_or_none()


def link_student_to_user(db: Session, student_id: int, user_id: int) -> Student:
    statement = select(Student).where(Student.id == student_id)
    result = db.execute(statement)
    student = result.scalar_one_or_none()

    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Student not found"
        )

    statement = select(User).where(User.id == user_id)
    result = db.execute(statement)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if student.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="student already linked to user",
        )

    if user.student is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="user already linked to student",
        )

    student.user_id = user_id
    _invalidate_student_cache(student.id)

    try:
        db.commit()
        db.refresh(student)
        db.refresh(user)
        return student
    except StaleDataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student record has been modified by another transaction",
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Linking constraint failed: student or user already linked",
        )
