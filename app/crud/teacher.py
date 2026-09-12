from app.models import Teacher
from app.schemas import TeacherCreate, TeacherUpdate
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session


def create_teacher(db: Session, teacher: TeacherCreate) -> Teacher:
    new_teacher = Teacher(**teacher.model_dump())
    db.add(new_teacher)
    try:
        db.commit()
        db.refresh(new_teacher)
        return new_teacher
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Teacher constraint conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid teacher data provided",
        )


def update_teacher(
    db: Session, teacher_update: TeacherUpdate, teacher_id: int
) -> Teacher:
    statement = select(Teacher).where(Teacher.id == teacher_id)
    result = db.execute(statement)
    teacher = result.scalar_one_or_none()
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )

    if teacher_update.name is not None:
        teacher.name = teacher_update.name
    if teacher_update.department_id is not None:
        teacher.department_id = teacher_update.department_id

    try:
        db.commit()
        db.refresh(teacher)
        return teacher
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Teacher constraint conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid teacher data provided",
        )


def read_teacher(db: Session, teacher_id: int) -> Teacher:
    statement = select(Teacher).where(Teacher.id == teacher_id)
    result = db.execute(statement)
    teacher = result.scalar_one_or_none()
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )
    return teacher


def read_teachers(db: Session, skip: int = 0, limit: int = 100) -> list[Teacher]:
    statement = select(Teacher).order_by(Teacher.id).offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_teacher(db: Session, teacher_id: int) -> dict:
    statement = select(Teacher).where(Teacher.id == teacher_id)
    result = db.execute(statement)
    teacher = result.scalar_one_or_none()
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found"
        )

    db.delete(teacher)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete teacher due to assigned course offerings",
        )
    return {"message": "Teacher deleted successfully"}
