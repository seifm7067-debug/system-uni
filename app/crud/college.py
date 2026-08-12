from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models import College
from app.schemas import CollegeCreate, CollegeUpdate


def create_college(db: Session, college: CollegeCreate) -> College:
    new_college = College(**college.model_dump())
    db.add(new_college)
    try:
        db.commit()
        db.refresh(new_college)
        return new_college
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="College code or constraint conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid college data provided",
        )


def update_college(db: Session, college_update: CollegeUpdate, college_id: int) -> College:
    statement = select(College).where(College.id == college_id)
    result = db.execute(statement)
    college = result.scalar_one_or_none()
    if college is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="College not found")

    if college_update.name is not None:
        college.name = college_update.name
    if college_update.code is not None:
        college.code = college_update.code

    try:
        db.commit()
        db.refresh(college)
        return college
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="College code conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid college data provided",
        )


def read_college(db: Session, college_id: int) -> College:
    statement = select(College).where(College.id == college_id)
    result = db.execute(statement)
    college = result.scalar_one_or_none()
    if college is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="College not found")
    return college


def read_colleges(db: Session, skip: int = 0, limit: int = 100) -> list[College]:
    statement = select(College).offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_college(db: Session, college_id: int) -> dict:
    statement = select(College).where(College.id == college_id)
    result = db.execute(statement)
    college = result.scalar_one_or_none()
    if college is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="College not found")

    db.delete(college)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete college due to dependent records (e.g. departments)",
        )
    return {"message": "College deleted successfully"}
