from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.models import Department
from app.schemas import DepartmentCreate, DepartmentUpdate


def create_department(db: Session, department: DepartmentCreate) -> Department:
    new_department = Department(**department.model_dump())
    db.add(new_department)
    try:
        db.commit()
        db.refresh(new_department)
        return new_department
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department code or name conflict in this college",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid department data provided",
        )


def update_department(
    db: Session,
    department_update: DepartmentUpdate,
    department_id: int,
) -> Department:
    statement = select(Department).where(Department.id == department_id)
    result = db.execute(statement)
    department = result.scalar_one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    if department_update.name is not None:
        department.name = department_update.name
    if department_update.code is not None:
        department.code = department_update.code
    if department_update.college_id is not None:
        department.college_id = department_update.college_id

    try:
        db.commit()
        db.refresh(department)
        return department
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department code or name conflict",
        )
    except DataError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid department data provided",
        )


def read_department(db: Session, department_id: int) -> Department:
    statement = select(Department).where(Department.id == department_id)
    result = db.execute(statement)
    department = result.scalar_one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return department


def read_departments(db: Session, skip: int = 0, limit: int = 100) -> list[Department]:
    statement = select(Department).offset(skip).limit(limit)
    result = db.execute(statement)
    return result.scalars().all()


def delete_department(db: Session, department_id: int) -> dict:
    statement = select(Department).where(Department.id == department_id)
    result = db.execute(statement)
    department = result.scalar_one_or_none()
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")

    db.delete(department)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete department due to dependent records (teachers, students, courses)",
        )
    return {"message": "Department deleted successfully"}
