from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.crud.department import (
    create_department,
    delete_department,
    read_department,
    read_departments,
    update_department,
)
from app.database import get_db
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentResponseSchema,
    DepartmentUpdate,
)
from app.security.auth import require_admin, require_authenticated_user

router = APIRouter()


@router.post("/departments/", response_model=DepartmentResponseSchema, status_code=status.HTTP_201_CREATED)
def create_department_endpoint(
    department: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return create_department(db, department)


@router.get("/departments/{department_id}", response_model=DepartmentResponseSchema)
def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_department(db, department_id)


@router.get("/departments/", response_model=list[DepartmentResponseSchema])
def get_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_authenticated_user),
):
    return read_departments(db, skip=skip, limit=limit)


@router.put("/departments/{department_id}", response_model=DepartmentResponseSchema)
def update_department_endpoint(
    department_id: int,
    department: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return update_department(db, department, department_id)


@router.delete("/departments/{department_id}")
def delete_department_endpoint(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return delete_department(db, department_id)
